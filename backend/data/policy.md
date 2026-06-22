# E-Commerce Refund Policy

## 1. Refund Window
- Standard customers: refund allowed within 30 days of purchase date.
- Gold tier customers: extended refund window of 45 days.
- Refund window is calculated from the purchase_date to today's date.

## 2. Item Type Rules
- Physical items: eligible for refund if within the window and order status is "delivered".
- Digital items (e-books, courses, software): NOT eligible for refund under any circumstances, regardless of window. Digital goods are final sale.

## 3. Fraud Rule
- If a customer account is flagged for fraud (is_flagged = 1), ALL refund requests must be automatically denied, regardless of any other condition.

## 4. Order Status Rule
- Refunds can only be processed for orders with status "delivered".
- Orders with status "processing" or "cancelled" are not eligible (cancelled orders are already refunded by default; processing orders haven't shipped yet).

## 5. Approval Summary
A refund should be APPROVED only if ALL of these are true:
1. Customer is NOT flagged for fraud.
2. Order status is "delivered".
3. Item type is "physical" (not digital).
4. Order is within the refund window (30 days normal, 45 days for gold tier).

If any single condition fails, the refund must be DENIED, and the agent must clearly state which rule caused the denial.