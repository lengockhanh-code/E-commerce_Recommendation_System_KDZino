"use client";

import Link from "next/link";
import "./CategoryStrip.css";


const roundCategories = [

{
name:"Thời trang",
image:"https://images.unsplash.com/photo-1618354691373-d851c5c3a990?auto=format&fit=crop&w=150&q=80"
},

{
name:"Điện thoại",
image:"https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=150&q=80"
},

{
name:"Laptop",
image:"https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=150&q=80"
},

{
name:"Điện tử",
image:"https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?auto=format&fit=crop&w=150&q=80"
},

{
name:"Gia dụng",
image:"https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?auto=format&fit=crop&w=150&q=80"
},

{
name:"Làm đẹp",
image:"https://images.unsplash.com/photo-1556228720-195a672e8a03?auto=format&fit=crop&w=150&q=80"
},

{
name:"Thể thao",
image:"https://images.unsplash.com/photo-1614632537190-23e4146777db?auto=format&fit=crop&w=150&q=80"
},

{
name:"Nhà cửa",
image:"https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=150&q=80"
},

{
name:"Mẹ & Bé",
image:"https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?auto=format&fit=crop&w=150&q=80"
},

{
name:"Sách",
image:"https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?auto=format&fit=crop&w=150&q=80"
},

{
name:"Ô tô",
image:"https://images.unsplash.com/photo-1552519507-da3b142c6e3d?auto=format&fit=crop&w=150&q=80"
},

{
name:"Khác",
image:"https://cdn-icons-png.flaticon.com/512/1828/1828919.png"
}

];



export default function CategoryStrip(){


return (

<div className="category-strip">


{
roundCategories.map((item)=>(


<Link

href="/products"

key={item.name}

className="category-item"

>


<div className="category-image">


<img

src={item.image}

alt={item.name}

/>


</div>



<span>

{item.name}

</span>



</Link>


))
}


</div>

)

}