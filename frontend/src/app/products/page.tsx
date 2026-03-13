"use client";

import { useState } from "react";

interface Product {
  id: number;
  name: string;
  category: string;
  price: number;
  previousPrice: number | null;
  priceChange: number | null;
  lastUpdated: string;
}

const mockProducts: Product[] = [
  { id: 1, name: "Safety Shoes - Leather with PVC Sole", category: "Safety Shoes", price: 1250, previousPrice: 1300, priceChange: -3.85, lastUpdated: "2 hours ago" },
  { id: 2, name: "Industrial Safety Gloves", category: "Safety Gloves", price: 450, previousPrice: 450, priceChange: 0, lastUpdated: "3 hours ago" },
  { id: 3, name: "PVC Safety Boots", category: "Safety Footwear", price: 890, previousPrice: 850, priceChange: 4.71, lastUpdated: "5 hours ago" },
  { id: 4, name: "Cotton Safety Gloves", category: "Safety Gloves", price: 120, previousPrice: 125, priceChange: -4.0, lastUpdated: "1 day ago" },
  { id: 5, name: "Steel Toe Cap Shoes", category: "Safety Shoes", price: 1800, previousPrice: 1800, priceChange: 0, lastUpdated: "1 day ago" },
];

export default function ProductsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [products] = useState<Product[]>(mockProducts);

  const filteredProducts = products.filter(
    (p) =>
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-black">Products</h1>
          <p className="text-gray-500 mt-1">Monitor scraped products and price changes</p>
        </div>
        <button className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800 transition-colors">
          Scrape New Products
        </button>
      </div>

      {/* Search and Filter */}
      <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm p-4 mb-6">
        <div className="flex gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search products..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
            />
          </div>
          <select className="px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black">
            <option value="">All Categories</option>
            <option value="safety-shoes">Safety Shoes</option>
            <option value="safety-gloves">Safety Gloves</option>
            <option value="safety-footwear">Safety Footwear</option>
          </select>
          <select className="px-4 py-2 border border-[#e5e5e5] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black">
            <option value="">All Price Changes</option>
            <option value="increased">Price Increased</option>
            <option value="decreased">Price Decreased</option>
            <option value="unchanged">Unchanged</option>
          </select>
        </div>
      </div>

      {/* Products Table */}
      <div className="bg-white rounded-xl border border-[#e5e5e5] shadow-sm overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left py-4 px-6 text-sm font-medium text-gray-500">Product</th>
              <th className="text-left py-4 px-6 text-sm font-medium text-gray-500">Category</th>
              <th className="text-right py-4 px-6 text-sm font-medium text-gray-500">Current Price</th>
              <th className="text-right py-4 px-6 text-sm font-medium text-gray-500">Change</th>
              <th className="text-left py-4 px-6 text-sm font-medium text-gray-500">Last Updated</th>
              <th className="text-right py-4 px-6 text-sm font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredProducts.map((product) => (
              <tr key={product.id} className="border-t border-[#e5e5e5]">
                <td className="py-4 px-6">
                  <p className="text-sm font-medium text-black">{product.name}</p>
                </td>
                <td className="py-4 px-6">
                  <span className="px-2 py-1 text-xs font-medium bg-gray-100 text-gray-700 rounded">
                    {product.category}
                  </span>
                </td>
                <td className="py-4 px-6 text-right">
                  <p className="text-sm font-medium text-black">₹{product.price.toLocaleString()}</p>
                  {product.previousPrice && product.previousPrice !== product.price && (
                    <p className="text-xs text-gray-500 line-through">
                      ₹{product.previousPrice.toLocaleString()}
                    </p>
                  )}
                </td>
                <td className="py-4 px-6 text-right">
                  {product.priceChange !== null && product.priceChange !== 0 ? (
                    <span
                      className={`text-sm font-medium ${
                        product.priceChange > 0 ? "text-red-600" : "text-green-600"
                      }`}
                    >
                      {product.priceChange > 0 ? "↑" : "↓"} {Math.abs(product.priceChange).toFixed(2)}%
                    </span>
                  ) : (
                    <span className="text-sm text-gray-400">—</span>
                  )}
                </td>
                <td className="py-4 px-6 text-sm text-gray-500">{product.lastUpdated}</td>
                <td className="py-4 px-6 text-right">
                  <button className="text-sm text-gray-500 hover:text-black mr-3">View</button>
                  <button className="text-sm text-gray-500 hover:text-black">History</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-6">
        <p className="text-sm text-gray-500">
          Showing {filteredProducts.length} of {products.length} products
        </p>
        <div className="flex gap-2">
          <button className="px-4 py-2 text-sm font-medium text-gray-500 border border-[#e5e5e5] rounded-lg hover:bg-gray-50">
            Previous
          </button>
          <button className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-gray-800">
            1
          </button>
          <button className="px-4 py-2 text-sm font-medium text-gray-500 border border-[#e5e5e5] rounded-lg hover:bg-gray-50">
            2
          </button>
          <button className="px-4 py-2 text-sm font-medium text-gray-500 border border-[#e5e5e5] rounded-lg hover:bg-gray-50">
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
