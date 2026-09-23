"use client";

import {
  FaTicketAlt,
  FaShieldAlt,
  FaShippingFast,
  FaCreditCard,
  FaSyncAlt,
  FaCheck,
  FaPercentage,
} from "react-icons/fa";

import "./BenefitsStrip.css";

const benefits = [
  {
    icon: <span className="benefit-ticket"><FaTicketAlt /><FaPercentage className="benefit-icon-detail" /></span>,
    title: "Voucher hấp dẫn",
    sub: "Giảm đến 200K",
  },
  {
    icon: <span className="benefit-shield"><FaShieldAlt /><FaCheck className="benefit-icon-detail" /></span>,
    title: "Sản phẩm chính hãng",
    sub: "100% cam kết chính hãng",
  },
  {
    icon: <FaShippingFast />,
    title: "Giao hàng toàn quốc",
    sub: "Nhanh chóng - An toàn",
  },
  {
    icon: <FaCreditCard />,
    title: "Thanh toán tiện lợi",
    sub: "Nhiều phương thức",
  },
  {
    icon: <FaSyncAlt />,
    title: "Đổi trả dễ dàng",
    sub: "Trong 7 ngày",
  },
];

export default function BenefitsStrip() {
  return (
    <div className="benefits-strip">
      {benefits.map((item, index) => (
        <div className="benefit-item" key={index}>
          <div className="benefit-icon" aria-hidden="true">{item.icon}</div>
          <div className="benefit-text-box">
            <div className="benefit-title">{item.title}</div>
            <div className="benefit-sub">{item.sub}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
