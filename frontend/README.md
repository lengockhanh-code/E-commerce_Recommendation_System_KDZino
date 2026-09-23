# MerRec frontend

Next.js App Router, React và TypeScript. Dùng CSS thuần trong `src/app/globals.css`.

## Chạy dự án

Yêu cầu Node.js >= 20.9 và npm. Chạy trong thư mục `frontend`:

```sh
npm ci
npm run dev
```

Mở http://localhost:3000. Trên PowerShell nếu `npm.ps1` bị chặn, dùng `npm.cmd` thay `npm`.

```sh
npm run lint
npm run typecheck
npm run build
npm start
```

`npm start` phục vụ bản production sau khi build thành công.

## Cấu trúc

```text
frontend/
├── public/                 # Ảnh, font và tài nguyên tĩnh
├── src/
│   ├── app/
│   │   ├── layout.tsx      # Layout gốc, metadata, CSS toàn cục
│   │   ├── page.tsx        # Trang chủ /
│   │   ├── globals.css
│   │   ├── not-found.tsx
│   │   ├── (auth)/         # Nhóm route xác thực, không thêm vào URL
│   │   │   ├── layout.tsx
│   │   │   ├── login/page.tsx
│   │   │   └── register/page.tsx
│   │   ├── products/page.tsx
│   │   ├── cart/page.tsx
│   │   ├── profile/page.tsx
│   │   └── recommendations/page.tsx
│   ├── components/         # Thành phần giao diện tái sử dụng
│   └── lib/                # Hàm tiện ích và API client
├── eslint.config.mjs
├── next.config.ts
├── tsconfig.json
├── package.json
└── package-lock.json
```

- `@/*` trỏ tới `src/*`, ví dụ `@/components/Navbar`.
- `page.tsx` khai báo trang; `layout.tsx` dùng chung bố cục cho các trang bên dưới.
- `(auth)` là route group: hai URL là `/login` và `/register`.
- Component mặc định chạy phía server. Chỉ thêm `"use client"` khi cần state, sự kiện hoặc API trình duyệt.
- Component chỉ dùng riêng một route có thể đặt trong thư mục `_components` của route đó.
- `public/logo.png` được truy cập qua `/logo.png`.
- Đặt biến môi trường cục bộ trong `.env.local` tại `frontend/`; chỉ biến có tiền tố `NEXT_PUBLIC_` được công khai cho trình duyệt. Không đặt bí mật vào các biến đó.

Đây là bộ khung chạy được. Các trang nghiệp vụ và xác thực mới có nội dung giữ chỗ; chưa tích hợp backend. `lib/api.ts` và các component sản phẩm/giỏ hàng hiện vẫn là file TODO để triển khai tiếp.

Tham khảo: https://nextjs.org/docs/app/getting-started/project-structure
