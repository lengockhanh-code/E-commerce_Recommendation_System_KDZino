import "./login.css";

export default function LoginPage() {
    return (
        <>
            <div className="auth-page">

                <div className="auth-card">

                    <div className="auth-left">

                        <h1>Đăng nhập</h1>

                        <p className="auth-desc">
                           Đăng nhập tài khoản KDZ để quản lý đơn hàng,
                            lưu sản phẩm yêu thích và tận hưởng trải nghiệm mua sắm tiện lợi hơn.
                        </p>

                        <div className="auth-line-left"></div>

                        <a href="/auth/google" className="google-btn">
                            <i className="fa-brands fa-google"></i>
                            Đăng nhập bằng Google
                        </a>

                    </div>


                    <div className="auth-line"></div>


                    <div className="auth-right">

                        <form>

                            <input
                                type="email"
                                placeholder="Email"
                            />

                            <input
                                type="password"
                                placeholder="Mật khẩu"
                            />


                            <button type="submit">
                                Đăng nhập
                            </button>


                        </form>


                        <div className="auth-switch">
                            Chưa có tài khoản?
                            <a href="/register">
                                Đăng ký ngay
                            </a>
                        </div>


                    </div>


                </div>


            </div>
        </>
    );
}