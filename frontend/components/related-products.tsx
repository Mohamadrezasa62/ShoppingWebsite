"use client";
import { useEffect, useState } from "react";
type Product = {id:number; title:string; slug:string; price_toman:number};
export function RelatedProducts({productId}:{productId:number}){const[rows,setRows]=useState<Product[]>([]);useEffect(()=>{let active=true;fetch(`/api/v1/catalog/products/${productId}/related/`).then(async r=>{if(!r.ok)return;const data=await r.json();if(active)setRows(data.products);}).catch(()=>{});return()=>{active=false;};},[productId]);return rows.length?<section className="seller-section"><h2>محصولات مرتبط</h2><ul className="admin-list">{rows.map(row=><li key={row.id}><a href={`/products/${encodeURIComponent(row.slug)}/`}>{row.title}</a><p>{row.price_toman.toLocaleString("fa-IR")} تومان</p></li>)}</ul></section>:null;}
