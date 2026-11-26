# NexaMart Multi-Vendor Backend — Complete API Specification

> **Base URL:** `http://127.0.0.1:8000/api/v1/`  
> **Auth Prefix:** `Authorization: JWT <access_token>`  
> **Swagger UI:** `http://127.0.0.1:8000/swagger/`  
> **ReDoc UI:** `http://127.0.0.1:8000/redoc/`  

---

## 1. Authentication & Roles

* **Single Account Architecture:** Every user can be a buyer and a seller with the same credentials.
* **Seller Status Flow:** `pending` ➔ `approved` (by Admin) ➔ `suspended`.
* **Roles:**
  * **Public:** Browse categories, products, and store profiles.
  * **Customer (Authenticated):** Manage cart, place orders, cancel own orders, write reviews.
  * **Approved Seller (`IsApprovedSeller`):** Manage own products, view own sub-orders, update tracking & fulfillment status, view earnings summary.
  * **Admin (`is_staff: true`):** Approve/suspend sellers, manage all products and sub-orders.

---

## 2. Multi-Seller / Marketplace APIs

### 2.1 Seller Onboarding & Profile
| Method | Endpoint | Description | Auth Required | Payload |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/sellers/apply/` | Apply to become a seller (Status starts as `pending`) | **JWT** | `store_name`, `description`, `phone`, `logo` (optional) |
| `GET` | `/seller/profile/` | Get current seller's store profile and status | **JWT** | None |
| `PATCH` | `/seller/profile/` | Update current seller's store profile | **JWT** | `store_name`, `description`, `phone`, `logo` |

#### Apply Payload:
```json
{
  "store_name": "Fashion Hub",
  "description": "Premium apparel retailer",
  "phone": "01700000000"
}
```

---

### 2.2 Seller Catalog Management (`/seller/products/`)
Only approved sellers (`status: 'approved'`) can access these endpoints. All queries are strictly scoped to the seller's own products.

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/seller/products/` | List only the logged-in seller's products (paginated) | **Approved Seller** |
| `POST` | `/seller/products/` | Add a new product (Auto-assigns `seller`) | **Approved Seller** |
| `GET` | `/seller/products/{id}/` | Get details of seller's product | **Approved Seller** |
| `PATCH` | `/seller/products/{id}/` | Update seller's product | **Approved Seller** |
| `DELETE` | `/seller/products/{id}/` | Delete seller's product | **Approved Seller** |
| `GET` | `/seller/products/{product_id}/images/` | List images for seller's product | **Approved Seller** |
| `POST` | `/seller/products/{product_id}/images/` | Upload image for seller's product | **Approved Seller** |
| `DELETE` | `/seller/products/{product_id}/images/{id}/` | Delete product image | **Approved Seller** |

---

### 2.3 Seller Order Dashboard & Fulfillment (`/seller/orders/`)
When a customer buys items from multiple sellers in one cart, NexaMart creates an individual **SubOrder** for each seller.

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/seller/orders/` | List sub-orders containing this seller's products | **Approved Seller** |
| `GET` | `/seller/orders/?status=pending` | Filter sub-orders by status (`pending`, `confirmed`, `shipped`, `delivered`, `canceled`) | **Approved Seller** |
| `GET` | `/seller/orders/{id}/` | Get full sub-order detail (includes buyer address and phone) | **Approved Seller** |
| `PATCH` | `/seller/orders/{id}/status/` | Update sub-order fulfillment status and tracking number | **Approved Seller** |

#### Update SubOrder Status Payload:
```json
{
  "status": "shipped",
  "tracking_number": "TRK-88997766"
}
```

---

### 2.4 Seller Earnings & Financial Summary
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/seller/earnings/` | Get financial overview (net earnings, pending payouts, commission paid) | **Approved Seller** |

#### Earnings Response Example:
```json
{
  "total_sub_orders": 12,
  "delivered_sub_orders": 8,
  "pending_sub_orders": 3,
  "canceled_sub_orders": 1,
  "total_revenue": "18500.00",
  "total_commission_paid": "1850.00",
  "net_earnings": "16650.00",
  "pending_earnings": "4500.00"
}
```

---

### 2.5 Public Storefront APIs (For All Visitors)
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/stores/` | List all approved marketplace stores | No |
| `GET` | `/stores/{slug}/` | View public store profile, total products, average rating & review count | No |
| `GET` | `/stores/{slug}/products/` | Browse all active products by this specific seller | No |

---

### 2.6 Store Reviews APIs
| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/stores/{slug}/reviews/` | List customer reviews for this store | No |
| `POST` | `/stores/{slug}/reviews/` | Submit review & rating (1 to 5) for store | **Customer** |
| `PATCH` | `/stores/{slug}/reviews/{id}/` | Edit own review | **Author / Staff** |
| `DELETE` | `/stores/{slug}/reviews/{id}/` | Delete own review | **Author / Staff** |

#### Review Payload:
```json
{
  "rating": 5,
  "comment": "Authentic products and very fast shipping!"
}
```

---

### 2.7 Seller Coupon Management (`/seller/coupons/`)
Approved sellers can create and manage discount codes for their own store.

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/seller/coupons/` | List all coupons created for this seller's store | **Approved Seller** |
| `POST` | `/seller/coupons/` | Create a new coupon code | **Approved Seller** |
| `GET` | `/seller/coupons/{id}/` | Get details of specific coupon | **Approved Seller** |
| `PATCH` | `/seller/coupons/{id}/` | Update coupon dates, active status, or discounts | **Approved Seller** |
| `DELETE` | `/seller/coupons/{id}/` | Delete coupon | **Approved Seller** |

#### Create Coupon Payload:
```json
{
  "code": "SUMMER20",
  "discount_type": "percent",
  "discount_value": "20.00",
  "min_purchase": "1000.00",
  "valid_from": "2026-11-01T00:00:00Z",
  "valid_to": "2026-12-01T23:59:59Z",
  "active": true
}
```

---

### 2.8 Coupon Validation API
Used by frontend carts to validate a coupon code before purchase.

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `POST` | `/coupons/validate/` | Validate coupon and calculate discount | No / Optional Auth |

#### Validation Request:
```json
{
  "code": "SUMMER20",
  "store_slug": "fashion-hub",
  "cart_amount": 1500.00
}
```

#### Validation Response:
```json
{
  "valid": true,
  "code": "SUMMER20",
  "store_name": "Fashion Hub",
  "store_slug": "fashion-hub",
  "discount_type": "percent",
  "discount_value": "20.00",
  "discount_amount": 300.00,
  "cart_amount": 1500.00,
  "final_amount": 1200.00
}
```

---

## 3. Buyer & Core APIs

### 3.1 Customer Orders (Two-Level View)
* `POST /api/v1/orders/` (`{"cart_id": "<uuid>"}`): Automatically groups cart items by seller, calculates seller earnings and commissions, and creates sub-orders.
* `GET /api/v1/orders/`: Customer sees parent orders. Inside each order, the `sub_orders` list shows the distinct status of each seller's package!

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "Shipped",
  "total_price": "4000.00",
  "created_at": "2026-11-26T12:00:00Z",
  "sub_orders": [
    {
      "id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "seller_store_name": "Fashion Hub",
      "seller_slug": "fashion-hub",
      "status": "shipped",
      "tracking_number": "TRK-112233",
      "subtotal": "2500.00",
      "items": [...]
    },
    {
      "id": "6ba7b811-9dad-11d1-80b4-00c04fd430c8",
      "seller_store_name": "Shoe Planet",
      "seller_slug": "shoe-planet",
      "status": "pending",
      "tracking_number": null,
      "subtotal": "1500.00",
      "items": [...]
    }
  ]
}
```

### 3.2 Products & Filtering
* `GET /api/v1/products/`
* Filters:
  * `?category_id=1`
  * `?seller_id=2`
  * `?seller__slug=fashion-hub`
  * `?search=sneakers`
  * `?price__gt=500&price__lt=2500`
  * `?ordering=-price`
