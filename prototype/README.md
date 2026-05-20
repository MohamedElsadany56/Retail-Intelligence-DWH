# Supermarket Ordering Prototype

Full-stack Flask prototype for a supermarket customer dashboard.

## Run

```powershell
pip install -r requirements.txt
python prototype/app.py
```

Open:

```text
http://127.0.0.1:5000
```

## What It Uses

- `outputs/basket_items_category.csv` for the product-category catalog and basket co-occurrence.
- `outputs/association_rules_fpgrowth.csv` first, then Apriori/ECLAT as fallback, for recommendation ranking.
- `prototype/runtime/orders.db` for completed order storage.

The recommendation API accepts one or more selected cart items and returns the most frequent associated items using mined rules, with a basket co-occurrence fallback when an exact rule is not available.
