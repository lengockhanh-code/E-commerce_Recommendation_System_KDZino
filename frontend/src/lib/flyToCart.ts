"use client";

export function animateFlyToCart(
  startElement: HTMLElement | null,
  imgSrc?: string
) {
  if (typeof window === "undefined") return;

  const cartIcon = document.getElementById("header-cart-icon") || document.querySelector(".cart-badge");
  if (!cartIcon) return;

  let startRect: DOMRect | null = null;
  let imageSource = imgSrc || "";

  if (startElement) {
    startRect = startElement.getBoundingClientRect();
    if (!imageSource) {
      const img = startElement.querySelector("img");
      if (img && img.src) {
        imageSource = img.src;
      }
    }
  }

  if (!startRect || startRect.width === 0) {
    startRect = {
      top: window.innerHeight / 2,
      left: window.innerWidth / 2,
      width: 60,
      height: 60,
      bottom: window.innerHeight / 2 + 60,
      right: window.innerWidth / 2 + 60,
      x: window.innerWidth / 2,
      y: window.innerHeight / 2,
      toJSON: () => {}
    } as DOMRect;
  }

  const cartRect = cartIcon.getBoundingClientRect();

  // Create flying img clone
  const flyImg = document.createElement("img");
  flyImg.src = imageSource || "/products/demo.png";
  flyImg.style.position = "fixed";
  flyImg.style.zIndex = "9999999";
  flyImg.style.width = `${Math.min(startRect.width || 60, 80)}px`;
  flyImg.style.height = `${Math.min(startRect.height || 60, 80)}px`;
  flyImg.style.top = `${startRect.top}px`;
  flyImg.style.left = `${startRect.left}px`;
  flyImg.style.borderRadius = "50%";
  flyImg.style.objectFit = "cover";
  flyImg.style.boxShadow = "0 8px 24px rgba(0, 135, 81, 0.4)";
  flyImg.style.pointerEvents = "none";
  flyImg.style.transition = "all 1.3s cubic-bezier(0.22, 1, 0.36, 1)";

  document.body.appendChild(flyImg);

  // Trigger flying path
  requestAnimationFrame(() => {
    flyImg.style.top = `${cartRect.top + 8}px`;
    flyImg.style.left = `${cartRect.left + 8}px`;
    flyImg.style.width = "22px";
    flyImg.style.height = "22px";
    flyImg.style.opacity = "0.15";
    flyImg.style.transform = "scale(0.25) rotate(720deg)";
  });

  // Remove and bounce cart icon on completion
  setTimeout(() => {
    if (flyImg.parentNode) {
      flyImg.parentNode.removeChild(flyImg);
    }

    const badge = cartIcon.querySelector(".cart-badge") || cartIcon;
    if (badge) {
      badge.classList.add("cart-bounce-pop");
      setTimeout(() => {
        badge.classList.remove("cart-bounce-pop");
      }, 500);
    }
  }, 1300);
}
