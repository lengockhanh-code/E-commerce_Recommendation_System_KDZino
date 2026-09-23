import "./register.css";


export default function RegisterPage() {


    return (

        <div className="auth-page">


            <div className="auth-card">


                <div className="auth-left">


                    <h1>
                        Tạo tài khoản
                    </h1>


                    <p className="auth-desc">

                         Tạo tài khoản chỉ trong vài bước để mua sắm nhanh hơn,
                        theo dõi đơn hàng và nhận những ưu đãi dành riêng cho bạn.
                    </p>


                    <div className="auth-line-left"></div>


                </div>



                <div className="auth-line"></div>



                <div className="auth-right">


                    <form>


                        <input
                            placeholder="Họ"
                        />


                        <input
                            placeholder="Tên"
                        />



                        <div className="gender-group">


                            <label>

                                <input
                                    type="radio"
                                    name="gender"
                                    defaultChecked
                                />

                                Nam

                            </label>



                            <label>

                                <input
                                    type="radio"
                                    name="gender"
                                />

                                Nữ

                            </label>


                        </div>



                        <input
                            placeholder="Email"
                        />



                        <input
                            type="password"
                            placeholder="Mật khẩu"
                        />



                        <button>
                            Đăng ký
                        </button>



                    </form>



                </div>



            </div>



        </div>

    );
}