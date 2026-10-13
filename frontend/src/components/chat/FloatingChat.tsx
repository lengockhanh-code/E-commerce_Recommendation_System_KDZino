"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Edit,
  Minus,
  RotateCcw,
  Send,
  Tag,
  X,
} from "lucide-react";
import { formatVND, toVND, type Product } from "@/lib/merrecData";
import { addToCart } from "@/lib/cart";
import { useAuth } from "@/lib/auth-context";
import { trackEventClient } from "@/lib/recommendations-client";
import "./FloatingChat.css";

interface ChatMessage {
  id: string;
  sender: "buyer" | "seller";
  type: "text" | "offer" | "counter_offer";
  text?: string;
  offerPrice?: number;
  originalPrice?: number;
  note?: string;
  status?: string;
  time: string;
}

interface ConversationItem {
  id: string;
  shopName: string;
  avatarText?: string;
  avatarImg?: string;
  lastMessage: string;
  time: string;
  unreadCount?: number;
  online: boolean;
}

const DEFAULT_CONVERSATIONS: ConversationItem[] = [
  {
    id: "kdz-fashion",
    shopName: "KDZ Fashion",
    avatarText: "KDZ",
    lastMessage: "Shop có thể để 460.000đ nhé ...",
    time: "10:24",
    unreadCount: 2,
    online: true,
  },
  {
    id: "phone-store",
    shopName: "Phone Store",
    avatarImg: "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=100&q=80",
    lastMessage: "Dạ còn hàng bạn nhé!",
    time: "09:15",
    unreadCount: 1,
    online: false,
  },
  {
    id: "laptop-center",
    shopName: "Laptop Center",
    avatarImg: "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=100&q=80",
    lastMessage: "Sản phẩm này đã hết hàng r...",
    time: "Hôm qua",
    online: false,
  },
  {
    id: "my-pham-kdz",
    shopName: "Mỹ phẩm KDZ",
    avatarImg: "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=100&q=80",
    lastMessage: "Cảm ơn bạn đã ủng hộ ạ!",
    time: "12/10",
    online: false,
  },
  {
    id: "home-decor",
    shopName: "Home Decor",
    avatarImg: "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=100&q=80",
    lastMessage: "Dạ ok bạn nhé!",
    time: "10/10",
    online: false,
  },
];

const DEFAULT_PINNED_PRODUCT: Product = {
  id: "kdz-bag-01",
  name: "Túi xách nữ KDZ thời trang cao cấp",
  price: 500000,
  currency: "VND",
  originalPrice: 650000,
  discount: 23,
  image: "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=200&q=80",
  images: [
    "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=200&q=80",
  ],
  condition: "New",
  c0_name: "Thời trang",
  c0_display: "Thời trang",
  c1_name: "Túi xách",
  brand: "KDZ",
  inStock: true,
  stockCount: 25,
  stockKnown: true,
  description: "Túi xách nữ KDZ thời trang cao cấp",
  rating: 4.9,
  soldCount: 142,
};

export default function FloatingChat() {
  const router = useRouter();
  const { user } = useAuth();

  const [isOpen, setIsOpen] = useState(false);
  const [activeConvId, setActiveConvId] = useState("kdz-fashion");
  const [unreadTotal, setUnreadTotal] = useState(4); // Match Image 1 badge!
  const [pinnedProduct, setPinnedProduct] = useState<Product>(DEFAULT_PINNED_PRODUCT);
  const [currentPrice, setCurrentPrice] = useState<number>(500000);
  const [inputText, setInputText] = useState("");

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m-1",
      sender: "buyer",
      type: "text",
      text: "Chào shop, sản phẩm này còn không ạ?",
      time: "10:20",
    },
    {
      id: "m-2",
      sender: "seller",
      type: "text",
      text: "Dạ còn hàng bạn nhé! Túi có màu xanh và màu be ạ.",
      time: "10:21",
    },
    {
      id: "m-3",
      sender: "buyer",
      type: "offer",
      originalPrice: 500000,
      offerPrice: 430000,
      note: "Em xin giá này được không ạ? 😊",
      status: "Đang chờ phản hồi",
      time: "10:22",
    },
    {
      id: "m-4",
      sender: "seller",
      type: "text",
      text: "Shop có thể để 460.000đ nhé bạn. Nếu bạn đồng ý mình sẽ tạo đơn luôn ạ!",
      time: "10:24",
    },
    {
      id: "m-5",
      sender: "seller",
      type: "counter_offer",
      offerPrice: 460000,
      time: "10:24",
    },
  ]);

  // Offer modal state
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [offerInputPrice, setOfferInputPrice] = useState("430000");
  const [offerNote, setOfferNote] = useState("Em xin giá này được không ạ? 😊");
  const [activeChip, setActiveChip] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll messages
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  // Listen for custom event to open chat with product
  useEffect(() => {
    const handleOpenChat = (event: Event) => {
      const custom = event as CustomEvent<{ product?: Product; offer?: boolean }>;
      setIsOpen(true);
      setUnreadTotal(0);
      if (custom.detail?.product) {
        setPinnedProduct(custom.detail.product);
        const pVnd = toVND(custom.detail.product.price, custom.detail.product.currency) || 500000;
        setCurrentPrice(pVnd);
        const initialBid = Math.round((pVnd * 0.85) / 1000) * 1000;
        setOfferInputPrice(String(initialBid));
      }
      if (custom.detail?.offer) {
        setShowOfferModal(true);
      }
    };

    window.addEventListener("merrec:open-chat", handleOpenChat);
    return () => window.removeEventListener("merrec:open-chat", handleOpenChat);
  }, []);

  const handleToggleOpen = () => {
    setIsOpen((prev) => {
      const next = !prev;
      if (next) setUnreadTotal(0);
      return next;
    });
  };

  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed) return;

    const time = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
    setMessages((prev) => [
      ...prev,
      { id: `m-${Date.now()}`, sender: "buyer", type: "text", text: trimmed, time },
    ]);
    setInputText("");

    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `bot-${Date.now()}`,
          sender: "seller",
          type: "text",
          text: "Dạ shop đã nhận được tin nhắn! Shop sẽ hỗ trợ bạn ngay ạ.",
          time: new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }, 1500);
  };

  // Submit Offer (fires event: offer_make)
  const handleSendOffer = () => {
    const offered = parseInt(offerInputPrice.replace(/\D/g, ""), 10);
    const listed = toVND(pinnedProduct.price, pinnedProduct.currency) || currentPrice;

    if (!offered || offered <= 0) {
      alert("Vui lòng nhập giá đề nghị hợp lệ.");
      return;
    }

    // 1. Emit offer_make event to MerRec analytics & recommendation engine!
    void trackEventClient({
      item_id: pinnedProduct.id,
      event_type: "offer_make",
      source_page: "floating_chat",
      metadata: {
        offer_price: offered,
        original_price: listed,
        note: offerNote,
        product_name: pinnedProduct.name,
      },
    });

    const nowTime = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

    // 2. Add offer card to message history
    setMessages((prev) => [
      ...prev,
      {
        id: `offer-${Date.now()}`,
        sender: "buyer",
        type: "offer",
        originalPrice: listed,
        offerPrice: offered,
        note: offerNote,
        status: "Đang chờ phản hồi",
        time: nowTime,
      },
    ]);
    setShowOfferModal(false);

    // 3. Simulate seller counter offer after 2 seconds
    setTimeout(() => {
      const counterPrice = Math.round((offered + (listed - offered) * 0.45) / 1000) * 1000;
      const counterTime = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

      setMessages((prev) => [
        ...prev,
        {
          id: `reply-${Date.now()}`,
          sender: "seller",
          type: "text",
          text: `Shop có thể để ${formatVND(counterPrice)} nhé bạn. Nếu bạn đồng ý mình sẽ tạo đơn luôn ạ!`,
          time: counterTime,
        },
        {
          id: `counter-${Date.now()}`,
          sender: "seller",
          type: "counter_offer",
          offerPrice: counterPrice,
          time: counterTime,
        },
      ]);
    }, 2000);
  };

  const handleAcceptOffer = (price: number) => {
    setCurrentPrice(price);
    const nowTime = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

    setMessages((prev) => [
      ...prev,
      {
        id: `acc-${Date.now()}`,
        sender: "buyer",
        type: "text",
        text: `Dạ em đồng ý với giá ${formatVND(price)} của shop ạ!`,
        time: nowTime,
      },
    ]);
  };

  // Buy Now: Emits buy_start event and proceeds to checkout
  const handleBuyNow = () => {
    void trackEventClient({
      item_id: pinnedProduct.id,
      event_type: "buy_start",
      source_page: "floating_chat",
      metadata: {
        price: currentPrice,
        negotiated: currentPrice < (toVND(pinnedProduct.price, pinnedProduct.currency) || 500000),
      },
    });

    addToCart(
      {
        ...pinnedProduct,
        price: currentPrice,
        currency: "VND",
      },
      1
    );

    if (!user) {
      router.push("/login?redirect=/checkout");
      return;
    }
    router.push("/checkout");
  };

  const currentListedVnd = toVND(pinnedProduct.price, pinnedProduct.currency) || 500000;

  return (
    <div className="floating-chat-root">
      {/* 1. EXPANDED CHAT WINDOW (WHEN OPEN) */}
      {isOpen && (
        <div className="floating-chat-window">
          {/* CỘT TRÁI: DANH SÁCH CUỘC TRÒ CHUYỆN */}
          <div className="docked-chat-sidebar">
            <div className="docked-sidebar-header">
              <span className="docked-sidebar-title">Chat</span>
              <div className="docked-sidebar-actions">
                <button
                  type="button"
                  className="docked-sidebar-btn"
                  title="Soạn tin nhắn"
                  onClick={() => alert("Chức năng tìm người bán mới")}
                >
                  <Edit size={14} />
                </button>
              </div>
            </div>

            <div className="docked-conv-list">
              {DEFAULT_CONVERSATIONS.map((c) => (
                <div
                  key={c.id}
                  className={`docked-conv-item ${activeConvId === c.id ? "active" : ""}`}
                  onClick={() => setActiveConvId(c.id)}
                >
                  <div className="docked-avatar-box">
                    <div className="docked-avatar-circle">
                      {c.avatarImg ? (
                        <img src={c.avatarImg} alt={c.shopName} />
                      ) : (
                        <span>{c.avatarText || "KDZ"}</span>
                      )}
                    </div>
                    {c.online && <span className="docked-online-dot" />}
                  </div>

                  <div className="docked-conv-content">
                    <div className="docked-conv-row1">
                      <span className="docked-conv-name">{c.shopName}</span>
                      <span className="docked-conv-time">{c.time}</span>
                    </div>
                    <div className="docked-conv-row2">
                      <span className="docked-conv-msg">{c.lastMessage}</span>
                      {c.unreadCount ? (
                        <span className="docked-conv-unread">{c.unreadCount}</span>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* CỘT PHẢI: KHUNG CHAT VỚI NGƯỜI BÁN */}
          <div className="docked-chat-main">
            {/* Header */}
            <div className="docked-chat-header">
              <div className="docked-header-seller">
                <div className="docked-seller-title">
                  <span className="docked-seller-name">KDZ Fashion</span>
                  <span className="docked-seller-status">Đang hoạt động</span>
                </div>
              </div>

              <div className="docked-header-actions">
                <button
                  type="button"
                  className="docked-window-btn"
                  title="Thu nhỏ"
                  onClick={() => setIsOpen(false)}
                >
                  <Minus size={15} />
                </button>
                <button
                  type="button"
                  className="docked-window-btn"
                  title="Đóng"
                  onClick={() => setIsOpen(false)}
                >
                  <X size={15} />
                </button>
              </div>
            </div>

            {/* Pinned Product Card */}
            <div className="docked-pinned-product">
              <div className="docked-pinned-info">
                <img
                  src={pinnedProduct.image || DEFAULT_PINNED_PRODUCT.image}
                  alt={pinnedProduct.name}
                  className="docked-pinned-img"
                />
                <div className="docked-pinned-text">
                  <span className="docked-pinned-name">{pinnedProduct.name}</span>
                  <span className="docked-pinned-price">
                    {formatVND(currentPrice || currentListedVnd)}
                  </span>
                </div>
              </div>

              <div className="docked-pinned-btns">
                <button type="button" className="btn-docked-buy" onClick={handleBuyNow}>
                  Mua ngay
                </button>
                <button
                  type="button"
                  className="btn-docked-offer"
                  onClick={() => setShowOfferModal(true)}
                >
                  Trả giá
                </button>
              </div>
            </div>

            {/* Messages Body */}
            <div className="docked-messages-body">
              {messages.map((m) => {
                if (m.type === "offer") {
                  return (
                    <div key={m.id} className="docked-msg-row buyer">
                      <div className="docked-offer-card">
                        <div className="docked-offer-header">
                          <span>🏷️ Đề nghị giá</span>
                          <span className="docked-offer-status">
                            {m.status || "Đang chờ"}
                          </span>
                        </div>
                        <div className="docked-offer-body">
                          <div>{pinnedProduct.name}</div>
                          <div className="docked-offer-price-row">
                            <span style={{ color: "#6b7280" }}>
                              Giá gốc: {formatVND(m.originalPrice || currentListedVnd)}
                            </span>
                            <span className="docked-offer-bid">
                              Đề nghị: {formatVND(m.offerPrice || 430000)}
                            </span>
                          </div>
                          {m.note && (
                            <div style={{ color: "#374151", fontStyle: "italic", marginTop: 4 }}>
                              &ldquo;{m.note}&rdquo;
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                }

                if (m.type === "counter_offer") {
                  return (
                    <div key={m.id} className="docked-msg-row seller">
                      <div className="docked-seller-avt">KDZ</div>
                      <div className="docked-counter-card">
                        <div className="docked-counter-header">
                          <RotateCcw size={13} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
                          Shop đề xuất: {formatVND(m.offerPrice || 460000)}
                        </div>
                        <div className="docked-counter-actions">
                          <button
                            type="button"
                            className="btn-docked-accept"
                            onClick={() => handleAcceptOffer(m.offerPrice || 460000)}
                          >
                            Chấp nhận
                          </button>
                          <button
                            type="button"
                            className="btn-docked-negotiate"
                            onClick={() => setShowOfferModal(true)}
                          >
                            Thương lượng
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                }

                return (
                  <div
                    key={m.id}
                    className={`docked-msg-row ${m.sender === "buyer" ? "buyer" : "seller"}`}
                  >
                    {m.sender === "seller" && <div className="docked-seller-avt">KDZ</div>}
                    <div
                      className={
                        m.sender === "buyer" ? "docked-bubble-buyer" : "docked-bubble-seller"
                      }
                    >
                      {m.text}
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <form className="docked-input-bar" onSubmit={handleSendMessage}>
              <input
                type="text"
                className="docked-input-field"
                placeholder="Nhập tin nhắn..."
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
              />
              <button type="submit" className="docked-send-btn" title="Gửi">
                <Send size={15} />
              </button>
              <button
                type="button"
                className="docked-offer-btn"
                title="Trả giá"
                onClick={() => setShowOfferModal(true)}
              >
                <Tag size={13} /> Trả giá
              </button>
            </form>

            {/* Modal Trả giá in Docked Chat */}
            {showOfferModal && (
              <div className="docked-modal-overlay">
                <div className="docked-modal-card">
                  <div className="docked-modal-header">
                    <h4>Đề nghị giá sản phẩm</h4>
                    <button
                      type="button"
                      className="docked-modal-close"
                      onClick={() => setShowOfferModal(false)}
                    >
                      <X size={16} />
                    </button>
                  </div>

                  <div style={{ fontSize: 12, color: "#4b5563", marginBottom: 8 }}>
                    Giá niêm yết: <strong>{formatVND(currentListedVnd)}</strong>
                  </div>

                  <div className="docked-quick-chips">
                    {[
                      { label: "-5%", pct: 0.95 },
                      { label: "-10%", pct: 0.9 },
                      { label: "-14%", val: 430000 },
                      { label: "-20%", pct: 0.8 },
                    ].map((opt, i) => {
                      const val = opt.val || Math.round((currentListedVnd * (opt.pct || 1)) / 1000) * 1000;
                      return (
                        <button
                          key={i}
                          type="button"
                          className={`docked-chip-btn ${activeChip === i ? "active" : ""}`}
                          onClick={() => {
                            setActiveChip(i);
                            setOfferInputPrice(String(val));
                          }}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>

                  <div className="docked-form-field">
                    <label>Giá mong muốn (VNĐ)</label>
                    <input
                      type="text"
                      value={offerInputPrice}
                      onChange={(e) => {
                        setOfferInputPrice(e.target.value);
                        setActiveChip(null);
                      }}
                      placeholder="Nhập giá..."
                    />
                  </div>

                  <div className="docked-form-field">
                    <label>Lời nhắn (tùy chọn)</label>
                    <textarea
                      rows={2}
                      value={offerNote}
                      onChange={(e) => setOfferNote(e.target.value)}
                      placeholder="Em xin giá này được không ạ?..."
                    />
                  </div>

                  <div className="docked-modal-actions">
                    <button
                      type="button"
                      className="btn-docked-cancel"
                      onClick={() => setShowOfferModal(false)}
                    >
                      Hủy
                    </button>
                    <button
                      type="button"
                      className="btn-docked-submit"
                      onClick={handleSendOffer}
                    >
                      Gửi đề nghị
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 2. THE DOCKED TAB BUTTON AT THE BOTTOM (EXACTLY MATCHING IMAGE 1) */}
      <button
        type="button"
        className="floating-chat-trigger"
        onClick={handleToggleOpen}
        aria-label="Mở khung chat"
      >
        <span className="floating-chat-icon-wrap">
          {/* Shopee style smiling chat bubble */}
          <svg width="22" height="20" viewBox="0 0 24 22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="#ffffff" stroke="none" />
            <path d="M8 10c.8 1 2.2 1.5 4 1.5s3.2-.5 4-1.5" stroke="#ee4d2d" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </span>
        <span className="floating-chat-label">Chat</span>

        {unreadTotal > 0 && !isOpen && (
          <span className="floating-chat-badge">{unreadTotal}</span>
        )}

        <span className="floating-chat-arrow">
          {isOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </span>
      </button>
    </div>
  );
}
