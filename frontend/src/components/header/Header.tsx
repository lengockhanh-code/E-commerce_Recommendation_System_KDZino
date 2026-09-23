"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCart } from "@/lib/cart";
import "./Header.css";
import {
  UserIcon,
  CartIcon,
  SearchIcon,
} from "@/components/icons/HeaderIcons";


export default function Header() {

  const pathname = usePathname();
  const { items } = useCart();


  return (

    <header className="header">


      {/* MAIN HEADER */}

      <div className="top-header">


        <Link href="/" className="logo">

          <Image
            src="/kdz_logo.png"
            alt="KDZ"
            width={190}
            height={75}
            priority
            style={{
              objectFit: "contain"
            }}
          />

        </Link>



        {/* SEARCH */}

        <div className="search">

          <input
            type="text"
            aria-label="Tìm kiếm sản phẩm"
            placeholder="Tìm kiếm sản phẩm, thương hiệu, danh mục..."
          />

          <button className="search-btn" aria-label="Tìm kiếm">

            <SearchIcon/>

          </button>

        </div>



        {/* ACTION */}

        <div className="actions">

          {/* TÀI KHOẢN */}
          <Link
            href="/profile"
            className="action-item"
          >
            <span className="icon">
              <UserIcon />
            </span>
            <div>
              <p>Tài khoản</p>
              <small>Đăng nhập / Đăng ký</small>
            </div>
          </Link>

          {/* GIỎ HÀNG */}
          <Link
            href="/cart"
            className="action-item"
          >
            <span className="icon">
              <CartIcon />
            </span>
            <div>
              <p>Giỏ hàng</p>
              <small>{items.reduce((sum, item) => sum + item.qty, 0)} sản phẩm</small>
            </div>
          </Link>

        </div>



      </div>





      {/* NAVIGATION */}

      <nav className="sub-nav">


        <div className="sub-nav-content">
          <div className="nav-links">


            <Link
              href="/"
              className={
                `nav-link-item ${
                  pathname === "/" ? "active" : ""
                }`
              }
            >

              Trang chủ

            </Link>





            <Link
              href="/products"
              className={
                `nav-link-item ${
                  pathname.startsWith("/products")
                  ? "active"
                  : ""
                }`
              }
            >

              Sản phẩm

            </Link>





            <Link
              href="#"
              className="nav-link-item"
            >

              Khuyến mãi

            </Link>





            <Link
              href="/mall"
              className={
                `nav-link-item ${
                  pathname.startsWith("/mall")
                  ? "active"
                  : ""
                }`
              }
            >

              Mall

            </Link>











            <Link
              href="#"
              className="nav-link-item"
            >

              Tin tức

            </Link>





            <Link
              href="#"
              className="nav-link-item"
            >

              Về KDZ

            </Link>



          </div>


        </div>


      </nav>



    </header>

  );

}
