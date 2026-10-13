"""History-aware Two-Tower shared by export, evaluation and serving.

Histories contain TRAIN-universe item indices, oldest first. Unknown items are
removed by callers; unknown users use -1 and can still be encoded from history.
The notebook embeds this implementation so Kaggle does not need the repository.
"""
from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F


class HistoryTwoTower(nn.Module):
    def __init__(self, cfg, n_users):
        super().__init__()
        self.cfg = dict(cfg)
        d, fd, h = cfg['embed_dim'], cfg['feature_dim'], cfg['hidden_dim']
        self.user = nn.Embedding(n_users, d, sparse=True)
        self.meta = nn.ModuleDict({k: nn.Embedding(v, fd, sparse=True)
                                  for k, v in cfg['hash_buckets'].items()})
        self.mlp = nn.Sequential(nn.Linear(len(self.meta)*fd+1, h), nn.ReLU(),
                                 nn.Dropout(cfg['dropout']), nn.Linear(h, d))
        self.user_mlp = nn.Sequential(nn.Linear(2*d, h), nn.ReLU(),
                                      nn.Dropout(cfg['dropout']), nn.Linear(h, d))
        nn.init.normal_(self.user.weight, std=.02)
        for e in self.meta.values():
            nn.init.normal_(e.weight, std=.02)

    def encode_item(self, x):
        z = [self.meta[k](x[k]) for k in self.meta] + [x['price_z'].unsqueeze(-1)]
        return F.normalize(self.mlp(torch.cat(z, dim=-1)), dim=-1)

    def encode_user(self, u, history_features, history_mask):
        known = (u >= 0) & (u < self.user.num_embeddings)
        identity = self.user(u.clamp(0, self.user.num_embeddings-1)) * known.unsqueeze(-1)
        vectors = self.encode_item(history_features)
        mask = history_mask.bool()
        if self.training and self.cfg.get('history_dropout', 0):
            mask = mask & (torch.rand(len(u), 1, device=u.device) >= self.cfg['history_dropout'])
        ages = torch.arange(mask.shape[1]-1, -1, -1, device=u.device)
        weights = self.cfg.get('history_decay', .9) ** ages.float()
        weights = mask.float() * weights.unsqueeze(0)
        pooled = (vectors * weights.unsqueeze(-1)).sum(1) / weights.sum(1).clamp_min(1e-8).unsqueeze(-1)
        return F.normalize(self.user_mlp(torch.cat((identity, pooled), dim=-1)), dim=-1)


def history_tensors(histories, item_features, cfg, device='cpu'):
    """Left-pad, retaining the most recent known events (including repeats)."""
    length = int(cfg['history_length'])
    if length <= 0:
        raise ValueError('history_length must be positive')
    ids = np.zeros((len(histories), length), dtype=np.int64)
    mask = np.zeros_like(ids, dtype=bool)
    n_items = len(item_features['price_z'])
    for row, history in enumerate(histories):
        valid = [int(i) for i in history if 0 <= int(i) < n_items][-length:]
        if valid:
            ids[row, -len(valid):] = valid
            mask[row, -len(valid):] = True
    features = {k: torch.as_tensor(np.asarray(values[ids]).copy(),
                                   dtype=torch.float32 if k == 'price_z' else torch.long,
                                   device=device) for k, values in item_features.items()}
    return features, torch.as_tensor(mask, device=device)


def uses_history(checkpoint):
    return 'user_mlp.0.weight' in checkpoint['model']


def load_history_model(checkpoint, feature_dir):
    cfg = checkpoint['cfg']
    # Keep mmap-backed checkpoint tensors; avoid a second full user embedding copy.
    with torch.device('meta'):
        model = HistoryTwoTower(cfg, checkpoint['model']['user.weight'].shape[0])
    model.load_state_dict(checkpoint['model'], assign=True)
    model.eval()
    features = {k: np.load(Path(feature_dir) / (k+'.npy'), mmap_mode='r')
                for k in [*cfg['hash_buckets'], 'price_z']}
    if any(len(a) != checkpoint['n_items'] for a in features.values()):
        raise ValueError('History feature cache does not match checkpoint item universe')
    return model, features


def user_queries(checkpoint, user_indices, histories=None, feature_dir=None,
                 loaded=None, batch_size=128):
    """Old checkpoints retain their exact ID-only behavior; new ones use history."""
    indices = np.asarray(user_indices, dtype=np.int64)
    known = (indices >= 0) & (indices < len(checkpoint['model']['user.weight']))
    if not uses_history(checkpoint):
        if not known.all():
            raise ValueError('Legacy Two-Tower requires a mapped TRAIN user')
        with torch.inference_mode():
            return F.normalize(checkpoint['model']['user.weight'][torch.as_tensor(indices)], dim=-1).numpy().astype(np.float32)
    if histories is None or len(histories) != len(indices):
        raise ValueError('Provide one ordered history per user')
    model, features = loaded if loaded is not None else load_history_model(checkpoint, feature_dir)
    output = []
    with torch.inference_mode():
        for start in range(0, len(indices), batch_size):
            x, mask = history_tensors(histories[start:start+batch_size], features, model.cfg)
            if np.any(~known[start:start+batch_size] & ~mask.any(1).numpy()):
                raise ValueError('Unknown user needs at least one mapped history item')
            q = model.encode_user(torch.as_tensor(indices[start:start+batch_size]), x, mask)
            output.append(q.numpy().astype(np.float32))
    return np.concatenate(output) if output else np.empty((0, model.cfg['embed_dim']), np.float32)
