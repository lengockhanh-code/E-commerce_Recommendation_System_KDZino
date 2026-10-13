"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Check,
  CheckCheck,
  Edit,
  Image as ImageIcon,
  MoreVertical,
  RotateCcw,
  Search,
  Send,
  ShoppingCart,
  Smile,
  Tag,
  X,
} from "lucide-react";
import { formatVND, toVND, type Product } from "@/lib/merrecData";
import { addToCart } from "@/lib/cart";
import { useAuth } from "@/lib/auth-context";
import { trackEventClient } from "@/lib/recommendations-client";
import "./chat.css";

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

interface Conversation {
  id: string;
  shopName: string;
  avatarText?: string;
  avatarImg?: string;
  lastMessage: string;
  time: string;
  unreadCount?: number;
  online: boolean;
}

const DEFAULT_CONVERSATIONS: Conversation[] = [
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
  {
    id: "the-thao-kdz",
    shopName: "Thể thao KDZ",
    avatarImg: "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?auto=format&fit=crop&w=100&q=80",
    lastMessage: "Bạn có thể xem thêm màu kh...",
    time: "08/10",
    online: false,
  },
  {
    id: "baby-shop",
    shopName: "Baby Shop",
    avatarImg: "https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?auto=format&fit=crop&w=100&q=80",
    lastMessage: "Sản phẩm này đang khuyến ...",
    time: "05/10",
    online: false,
  },
];

const DEFAULT_DEMO_PRODUCT: Product = {
  id: "kdz-bag-01",
  name: "Túi xách nữ KDZ thời trang cao cấp",
  price: 500000,
  currency: "VND",
  originalPrice: 650000,
  discount: 23,
  image: "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=400&q=80",
  images: [
    "https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=400&q=80",
  ],
  condition: "New",
  c0_name: "Thời trang",
  c0_display: "Thời trang",
  c1_name: "Túi xách",
  brand: "KDZ",
  inStock: true,
  stockCount: 25,
  stockKnown: true,
  description: "Túi xách nữ KDZ thời trang cao cấp, thiết kế thanh lịch sang trọng, phù hợp đi làm và dạo phố.",
  rating: 4.9,
  soldCount: 142,
};

function ChatView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const productId = searchParams.get("productId");
  const autoOffer = searchParams.get("offer") === "true";
  const { user } = useAuth();

  const [activeConv, setActiveConv] = useState("kdz-fashion");
  const [filterTab, setFilterTab] = useState<"all" | "unread" | "fav">("all");
  const [product, setProduct] = useState<Product>(DEFAULT_DEMO_PRODUCT);
  const [currentPrice, setCurrentPrice] = useState<number>(500000);
  const [inputText, setInputText] = useState("");
  const [toastMsg, setToastMsg] = useState("");

  // Timeline state
  const [timeline, setTimeline] = useState([
    {
      type: "buyer_offer",
      title: "Bạn đã đề nghị 430.000đ",
      sub: "10:22 - Đang chờ phản hồi",
      orange: true,
    },
    {
      type: "seller_counter",
      title: "Shop đề xuất 460.000đ",
      sub: "10:24",
      orange: false,
    },
  ]);

  // Messages list state
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
      text: "Chào bạn, sản phẩm này còn hàng nhé!",
      time: "10:20",
    },
    {
      id: "m-3",
      sender: "seller",
      type: "text",
      text: "Dạ túi còn màu xanh và màu be ạ.",
      time: "10:21",
    },
    {
      id: "m-4",
      sender: "buyer",
      type: "offer",
      originalPrice: 500000,
      offerPrice: 430000,
      note: "Em xin giá này được không ạ? 😊",
      status: "Đang chờ phản hồi",
      time: "10:22",
    },
    {
      id: "m-5",
      sender: "seller",
      type: "text",
      text: "Shop có thể để 460.000đ nhé bạn. Nếu bạn đồng ý mình sẽ tạo đơn luôn ạ!",
      time: "10:24",
    },
    {
      id: "m-6",
      sender: "seller",
      type: "counter_offer",
      offerPrice: 460000,
      time: "10:24",
    },
  ]);

  // Offer Modal State
  const [showOfferModal, setShowOfferModal] = useState(autoOffer);
  const [offerInputPrice, setOfferInputPrice] = useState("430000");
  const [offerNote, setOfferNote] = useState("Em xin giá này được không ạ? 😊");
  const [activeDiscount, setActiveDiscount] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load product if passed in URL
  useEffect(() => {
    if (!productId) return;
    fetch(`/api/products/${encodeURIComponent(productId)}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.name) {
          setProduct(data);
          const pVnd = toVND(data.price, data.currency);
          setCurrentPrice(pVnd);
          const initialBid = Math.round((pVnd * 0.85) / 1000) * 1000;
          setOfferInputPrice(String(initialBid));
        }
      })
      .catch(() => {});
  }, [productId]);

  // Auto scroll messages to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(""), 3500);
  };

  // Send a regular text message
  const handleSendMessage = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = inputText.trim();
    if (!trimmed) return;

    const newMsg: ChatMessage = {
      id: `m-${Date.now()}`,
      sender: "buyer",
      type: "text",
      text: trimmed,
      time: new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, newMsg]);
    setInputText("");

    // Simulate seller auto reply after 1.5s
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: `m-bot-${Date.now()}`,
          sender: "seller",
          type: "text",
          text: "Cảm ơn bạn đã nhắn tin! Shop sẽ kiểm tra và phản hồi lại bạn ngay nhé.",
          time: new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    }, 1500);
  };

  // Submit Offer
  const handleSendOffer = () => {
    const offered = parseInt(offerInputPrice.replace(/\D/g, ""), 10);
    const listed = toVND(product.price, product.currency) || currentPrice;

    if (!offered || offered <= 0) {
      alert("Vui lòng nhập giá đề nghị hợp lệ.");
      return;
    }

    if (offered >= listed) {
      alert("Giá đề nghị phải thấp hơn giá niêm yết của sản phẩm.");
      return;
    }

    // 1. Emit offer_make event to MerRec recommendation engine & analytics!
    void trackEventClient({
      item_id: product.id,
      event_type: "offer_make",
      source_page: "chat",
      metadata: {
        offer_price: offered,
        original_price: listed,
        note: offerNote,
        product_name: product.name,
      },
    });

    const nowTime = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });

    // 2. Add offer card to message history
    const offerMsg: ChatMessage = {
      id: `offer-${Date.now()}`,
      sender: "buyer",
      type: "offer",
      originalPrice: listed,
      offerPrice: offered,
      note: offerNote,
      status: "Đang chờ phản hồi",
      time: nowTime,
    };

    setMessages((prev) => [...prev, offerMsg]);
    setShowOfferModal(false);

    // 3. Update right sidebar timeline
    setTimeline([
      {
        type: "buyer_offer",
        title: `Bạn đã đề nghị ${formatVND(offered)}`,
        sub: `${nowTime} - Đang chờ phản hồi`,
        orange: true,
      },
    ]);

    showToast(`Đã gửi đề nghị ${formatVND(offered)} thành công! (Event: offer_make)`);

    // 4. Simulate realistic seller counter response after 2 seconds
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

      setTimeline((prev) => [
        ...prev,
        {
          type: "seller_counter",
          title: `Shop đề xuất ${formatVND(counterPrice)}`,
          sub: counterTime,
          orange: false,
        },
      ]);
    }, 2000);
  };

  // Accept counter offer
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

    setTimeline((prev) => [
      ...prev,
      {
        type: "accepted",
        title: `Đã chốt giá ${formatVND(price)}`,
        sub: `${nowTime} - Sẵn sàng tạo đơn`,
        orange: false,
      },
    ]);

    showToast(`Đã chốt giá ưu đãi ${formatVND(price)}! Bấm "Mua ngay" để thanh toán.`);
  };

  // Buy Now: Emits buy_start event and proceeds to checkout
  const handleBuyNow = () => {
    // 1. Emit buy_start event
    void trackEventClient({
      item_id: product.id,
      event_type: "buy_start",
      source_page: "chat",
      metadata: {
        price: currentPrice,
        negotiated: currentPrice < (toVND(product.price, product.currency) || 500000),
      },
    });

    // 2. Add item to cart with negotiated price
    addToCart(
      {
        ...product,
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

  // Add to cart from sidebar
  const handleAddToCart = () => {
    void trackEventClient({
      item_id: product.id,
      event_type: "cart",
      source_page: "chat",
      metadata: { price: currentPrice },
    });

    addToCart(
      {
        ...product,
        price: currentPrice,
        currency: "VND",
      },
      1
    );

    showToast("Đã thêm sản phẩm vào giỏ hàng thành công!");
  };

  const productPriceVnd = toVND(product.price, product.currency) || 500000;

  return (
    <div className="chat-page">
      <div className="chat-container">
        {/* ==================== CỘT 1: DANH SÁCH CUỘC TRÒ CHUYỆN ==================== */}
        <aside className="chat-sidebar">
          <div className="chat-sidebar-header">
            <h1>Tin nhắn</h1>
            <button className="chat-compose-btn" title="Soạn tin nhắn mới">
              <Edit size={16} />
            </button>
          </div>

          <div className="chat-search-box">
            <Search size={16} />
            <input type="text" placeholder="Tìm kiếm cuộc trò chuyện..." />
          </div>

          <div className="chat-filter-tabs">
            <button
              className={`chat-filter-tab ${filterTab === "all" ? "active" : ""}`}
              onClick={() => setFilterTab("all")}
            >
              Tất cả
            </button>
            <button
              className={`chat-filter-tab ${filterTab === "unread" ? "active" : ""}`}
              onClick={() => setFilterTab("unread")}
            >
              Chưa đọc
            </button>
            <button
              className={`chat-filter-tab ${filterTab === "fav" ? "active" : ""}`}
              onClick={() => setFilterTab("fav")}
            >
              Yêu thích
            </button>
          </div>

          <div className="chat-conv-list">
            {DEFAULT_CONVERSATIONS.map((c) => (
              <div
                key={c.id}
                className={`chat-conv-item ${activeConv === c.id ? "active" : ""}`}
                onClick={() => setActiveConv(c.id)}
              >
                <div className="chat-avatar-wrapper">
                  <div className="chat-avatar-circle">
                    {c.avatarImg ? (
                      <img src={c.avatarImg} alt={c.shopName} />
                    ) : (
                      <span>{c.avatarText || "KDZ"}</span>
                    )}
                  </div>
                  {c.online && <div className="chat-online-badge" />}
                </div>

                <div className="chat-conv-info">
                  <div className="chat-conv-row1">
                    <span className="chat-conv-name">{c.shopName}</span>
                    <span className={`chat-conv-time ${c.unreadCount ? "" : "gray"}`}>
                      {c.time}
                    </span>
                  </div>
                  <div className="chat-conv-row2">
                    <span className="chat-conv-snippet">{c.lastMessage}</span>
                    {c.unreadCount ? (
                      <span className="chat-conv-badge">{c.unreadCount}</span>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </aside>

        {/* ==================== CỘT 2: KHUNG CHAT CHÍNH ==================== */}
        <main className="chat-main">
          {/* Header */}
          <div className="chat-main-header">
            <div className="chat-header-seller">
              <div className="chat-seller-avatar">
                <span>KDZ</span>
              </div>
              <div className="chat-seller-title">
                <span className="chat-seller-name">KDZ Fashion</span>
                <span className="chat-seller-status">Đang hoạt động</span>
              </div>
            </div>

            <div className="chat-header-actions">
              <button
                type="button"
                className="chat-view-shop-btn"
                onClick={() => router.push("/products")}
              >
                Xem shop
              </button>
              <button type="button" className="chat-more-btn" title="Tùy chọn">
                <MoreVertical size={18} />
              </button>
            </div>
          </div>

          {/* Thẻ sản phẩm đang trao đổi trên cùng */}
          <div className="chat-pinned-product">
            <div className="chat-pinned-left">
              <img
                src={product.image || DEFAULT_DEMO_PRODUCT.image}
                alt={product.name}
                className="chat-pinned-img"
              />
              <div className="chat-pinned-info">
                <span className="chat-pinned-title">{product.name}</span>
                <span className="chat-pinned-price">{formatVND(productPriceVnd)}</span>
                <div className="chat-pinned-badges">
                  <span className="chat-pinned-badge-green">
                    <Check size={13} /> Còn hàng
                  </span>
                  <span>🛡️ Hàng chính hãng</span>
                  <span>🔄 Đổi trả 7 ngày</span>
                </div>
              </div>
            </div>

            <div className="chat-pinned-actions">
              <button
                type="button"
                className="btn-chat-buy-now"
                onClick={handleBuyNow}
              >
                Mua ngay
              </button>
              <button
                type="button"
                className="btn-chat-offer"
                onClick={() => setShowOfferModal(true)}
              >
                Trả giá
              </button>
            </div>
          </div>

          {/* Dòng tin nhắn */}
          <div className="chat-messages">
            {messages.map((m) => {
              if (m.type === "offer") {
                return (
                  <div key={m.id} className="msg-row buyer">
                    <div className="msg-offer-card-buyer">
                      <div className="offer-card-header">
                        <span className="offer-card-tag">
                          <Tag size={15} /> Đề nghị giá
                        </span>
                        <span className="offer-card-status-badge">
                          {m.status || "Đang chờ phản hồi"}
                        </span>
                      </div>

                      <div className="offer-product-box">
                        <img
                          src={product.image || DEFAULT_DEMO_PRODUCT.image}
                          alt={product.name}
                          className="offer-product-img"
                        />
                        <div className="offer-product-details">
                          <span className="offer-product-name">{product.name}</span>
                          <span className="offer-orig-price">
                            Giá niêm yết: {formatVND(m.originalPrice || productPriceVnd)}
                          </span>
                          <span className="offer-bid-price">
                            Giá đề nghị: {formatVND(m.offerPrice || 430000)}
                          </span>
                        </div>
                      </div>

                      {m.note && (
                        <div className="offer-user-note">
                          <strong>Lời nhắn:</strong> {m.note}
                        </div>
                      )}

                      <div className="msg-meta-buyer">
                        <span>{m.time}</span>
                        <CheckCheck size={14} />
                      </div>
                    </div>
                  </div>
                );
              }

              if (m.type === "counter_offer") {
                return (
                  <div key={m.id} className="msg-row seller">
                    <div className="msg-seller-avatar">KDZ</div>
                    <div className="msg-offer-card-seller">
                      <div className="counter-card-header">
                        <RotateCcw size={15} /> Phản hồi đề nghị giá
                      </div>

                      <div className="counter-product-box">
                        <img
                          src={product.image || DEFAULT_DEMO_PRODUCT.image}
                          alt={product.name}
                          className="counter-product-img"
                        />
                        <div className="counter-product-details">
                          <span className="offer-product-name">{product.name}</span>
                          <span className="offer-bid-price">
                            Giá shop đề xuất: {formatVND(m.offerPrice || 460000)}
                          </span>
                        </div>
                      </div>

                      <div className="counter-actions-row">
                        <button
                          type="button"
                          className="btn-counter-accept"
                          onClick={() => handleAcceptOffer(m.offerPrice || 460000)}
                        >
                          Chấp nhận
                        </button>
                        <button
                          type="button"
                          className="btn-counter-negotiate"
                          onClick={() => setShowOfferModal(true)}
                        >
                          Thương lượng tiếp
                        </button>
                      </div>

                      <div className="msg-meta-seller" style={{ marginTop: 8 }}>
                        <span>{m.time}</span>
                      </div>
                    </div>
                  </div>
                );
              }

              // Normal text bubbles
              return (
                <div
                  key={m.id}
                  className={`msg-row ${m.sender === "buyer" ? "buyer" : "seller"}`}
                >
                  {m.sender === "seller" && <div className="msg-seller-avatar">KDZ</div>}
                  <div
                    className={
                      m.sender === "buyer" ? "msg-bubble-buyer" : "msg-bubble-seller"
                    }
                  >
                    <span>{m.text}</span>
                    <div
                      className={
                        m.sender === "buyer" ? "msg-meta-buyer" : "msg-meta-seller"
                      }
                    >
                      <span>{m.time}</span>
                      {m.sender === "buyer" && <CheckCheck size={14} />}
                    </div>
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Khung nhập tin nhắn phía dưới */}
          <form className="chat-input-bar" onSubmit={handleSendMessage}>
            <button
              type="button"
              className="chat-input-icon-btn"
              title="Gửi hình ảnh"
              onClick={() => showToast("Chức năng gửi ảnh đính kèm")}
            >
              <ImageIcon size={20} />
            </button>
            <button
              type="button"
              className="chat-input-icon-btn"
              title="Biểu tượng cảm xúc"
              onClick={() => setInputText((prev) => prev + " 😊")}
            >
              <Smile size={20} />
            </button>

            <input
              type="text"
              className="chat-input-field"
              placeholder="Nhập tin nhắn..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
            />

            <button type="submit" className="chat-send-btn" title="Gửi tin nhắn">
              <Send size={17} />
            </button>

            <button
              type="button"
              className="chat-make-offer-btn"
              onClick={() => setShowOfferModal(true)}
            >
              <Tag size={16} /> Đề nghị giá
            </button>
          </form>
        </main>

        {/* ==================== CỘT 3: THÔNG TIN SẢN PHẨM & LỊCH SỬ ĐỀ NGHỊ ==================== */}
        <aside className="chat-info-sidebar">
          {/* Card 1: Thông tin sản phẩm */}
          <div className="chat-info-card">
            <h2 className="chat-info-card-title">Thông tin sản phẩm</h2>

            <div className="chat-info-product-top">
              <img
                src={product.image || DEFAULT_DEMO_PRODUCT.image}
                alt={product.name}
                className="chat-info-product-img"
              />
              <div className="chat-info-product-text">
                <span className="chat-info-product-name">{product.name}</span>
                <span className="chat-info-product-price">
                  {formatVND(currentPrice)}
                </span>
              </div>
            </div>

            <div className="chat-info-table">
              <div className="chat-info-row">
                <span className="chat-info-label">Tình trạng</span>
                <span className="chat-info-val green">Còn hàng</span>
              </div>
              <div className="chat-info-row">
                <span className="chat-info-label">Thương hiệu</span>
                <span className="chat-info-val">{product.brand || "KDZ"}</span>
              </div>
              <div className="chat-info-row">
                <span className="chat-info-label">Danh mục</span>
                <span className="chat-info-val">
                  {product.c0_name || "Thời trang"} &gt; {product.c1_name || "Túi xách"}
                </span>
              </div>
              <div className="chat-info-row">
                <span className="chat-info-label">Màu sắc</span>
                <div className="chat-color-swatches">
                  <span className="color-dot" style={{ background: "#009359" }} />
                  <span className="color-dot" style={{ background: "#f5d0a9" }} />
                  <span className="color-dot" style={{ background: "#111827" }} />
                </div>
              </div>
              <div className="chat-info-row">
                <span className="chat-info-label">Số lượng</span>
                <span className="chat-info-val">
                  {product.stockCount || 25} sản phẩm
                </span>
              </div>
            </div>

            <div className="chat-info-actions">
              <button
                type="button"
                className="btn-sidebar-buy-now"
                onClick={handleBuyNow}
              >
                Mua ngay
              </button>
              <button
                type="button"
                className="btn-sidebar-add-cart"
                onClick={handleAddToCart}
              >
                <ShoppingCart size={16} /> Thêm vào giỏ hàng
              </button>
            </div>
          </div>

          {/* Card 2: Lịch sử đề nghị giá */}
          <div className="chat-info-card">
            <h2 className="chat-info-card-title">Lịch sử đề nghị giá</h2>

            <div className="chat-timeline">
              {timeline.map((item, idx) => (
                <div key={idx} className="chat-timeline-step">
                  <div
                    className={`timeline-dot ${item.type === "seller_counter" ? "shop" : ""}`}
                  >
                    {item.type === "seller_counter" ? "KDZ" : <Check size={10} />}
                  </div>
                  <div className="timeline-title">{item.title}</div>
                  <div className={`timeline-sub ${item.orange ? "orange" : ""}`}>
                    {item.sub}
                  </div>
                </div>
              ))}
            </div>

            <div className="chat-timeline-actions">
              <button
                type="button"
                className="btn-timeline-accept"
                onClick={() => handleAcceptOffer(460000)}
              >
                Chấp nhận
              </button>
              <button
                type="button"
                className="btn-timeline-reject"
                onClick={() => {
                  showToast("Bạn đã từ chối đề nghị từ shop.");
                  setMessages((prev) => [
                    ...prev,
                    {
                      id: `rej-${Date.now()}`,
                      sender: "buyer",
                      type: "text",
                      text: "Dạ em xin phép chưa lấy giá này ạ, cảm ơn shop!",
                      time: new Date().toLocaleTimeString("vi-VN", {
                        hour: "2-digit",
                        minute: "2-digit",
                      }),
                    },
                  ]);
                }}
              >
                Từ chối
              </button>
            </div>
          </div>
        </aside>
      </div>

      {/* ==================== MODAL: ĐỀ NGHỊ GIÁ ==================== */}
      {showOfferModal && (
        <div
          className="offer-modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowOfferModal(false);
          }}
        >
          <div className="offer-modal">
            <div className="offer-modal-header">
              <h2>Đề nghị giá sản phẩm</h2>
              <button
                type="button"
                className="offer-modal-close"
                onClick={() => setShowOfferModal(false)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="offer-modal-product">
              <img
                src={product.image || DEFAULT_DEMO_PRODUCT.image}
                alt={product.name}
                className="offer-modal-pimg"
              />
              <div className="offer-modal-pinfo">
                <span className="offer-modal-pname">{product.name}</span>
                <span className="offer-modal-pprice">
                  Giá niêm yết: <strong>{formatVND(productPriceVnd)}</strong>
                </span>
              </div>
            </div>

            <label style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 6, display: "block" }}>
              Gợi ý giảm giá nhanh
            </label>
            <div className="offer-quick-discounts">
              {[
                { label: "-5%", pct: 0.95 },
                { label: "-10%", pct: 0.9 },
                { label: "-14% (430k)", val: 430000 },
                { label: "-20%", pct: 0.8 },
              ].map((opt, i) => {
                const targetVal = opt.val || Math.round((productPriceVnd * (opt.pct || 1)) / 1000) * 1000;
                return (
                  <button
                    key={i}
                    type="button"
                    className={`quick-discount-btn ${activeDiscount === i ? "active" : ""}`}
                    onClick={() => {
                      setActiveDiscount(i);
                      setOfferInputPrice(String(targetVal));
                    }}
                  >
                    {opt.label} ({formatVND(targetVal)})
                  </button>
                );
              })}
            </div>

            <div className="offer-form-group">
              <label htmlFor="offer-price-input">Giá đề nghị (VNĐ) *</label>
              <input
                id="offer-price-input"
                type="text"
                className="offer-input"
                value={offerInputPrice}
                onChange={(e) => {
                  setOfferInputPrice(e.target.value);
                  setActiveDiscount(null);
                }}
                placeholder="Nhập giá bạn mong muốn..."
              />
            </div>

            <div className="offer-form-group">
              <label htmlFor="offer-note-input">Lời nhắn gửi người bán</label>
              <textarea
                id="offer-note-input"
                className="offer-textarea"
                rows={2}
                value={offerNote}
                onChange={(e) => setOfferNote(e.target.value)}
                placeholder="Ví dụ: Em xin giá này được không ạ?..."
              />
            </div>

            <div className="offer-modal-footer">
              <button
                type="button"
                className="btn-modal-cancel"
                onClick={() => setShowOfferModal(false)}
              >
                Hủy
              </button>
              <button
                type="button"
                className="btn-modal-submit"
                onClick={handleSendOffer}
              >
                Gửi đề nghị giá
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TOAST POPUP */}
      {toastMsg && <div className="chat-toast">{toastMsg}</div>}
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: "center" }}>Đang tải tin nhắn...</div>}>
      <ChatView />
    </Suspense>
  );
}
