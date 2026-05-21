# Retail Intelligence Platform

An end-to-end retail data warehouse, business intelligence, and data mining project built on the **Dunnhumby Complete Journey** grocery retail dataset. The platform transforms raw retail data into a validated **Azure PostgreSQL** data warehouse, interactive **Power BI** dashboards, customer segmentation outputs, market basket analysis results, and a prototype recommendation engine.

**Repository:** <https://github.com/MohamedElsadany56/Retail-Intelligence-DWH.git>

---

## Table of Contents

- [1. Project Summary](#1-project-summary)
- [2. Business Problem](#2-business-problem)
- [3. Main Contributions](#3-main-contributions)
- [4. Technology Stack](#4-technology-stack)
- [5. Data Sources](#5-data-sources)
- [6. End-to-End Pipeline](#6-end-to-end-pipeline)
- [7. Data Cleaning Strategy](#7-data-cleaning-strategy)
- [8. Data Warehouse Design](#8-data-warehouse-design)
- [9. Data Quality Validation](#9-data-quality-validation)
- [10. Power BI Dashboards](#10-power-bi-dashboards)
- [11. Customer Segmentation](#11-customer-segmentation)
- [12. Market Basket Analysis](#12-market-basket-analysis)
- [13. Recommendation Prototype](#13-recommendation-prototype)
- [14. Project Structure](#14-project-structure)
- [15. Environment Variables](#15-environment-variables)
- [16. How to Run](#16-how-to-run)
- [17. Project Status](#17-project-status)
- [18. Team](#18-team)
- [19. Supervisor](#19-supervisor)
- [20. References](#20-references)

---

## 1. Project Summary

The **Retail Intelligence Platform** is a complete analytics system that starts from raw retail CSV files and ends with a business-ready intelligence layer. It combines:

- Python-based ETL and preprocessing
- Azure PostgreSQL data warehousing
- Dimensional modeling using fact and dimension tables
- Data validation and quality checks
- Power BI reporting
- Customer segmentation using clustering
- Market basket analysis using association rule mining
- Amazon-like recommendation prototype using mined rules

The project is positioned as both a **data warehouse / BI project** and a **data mining research project**.

---

## 2. Business Problem

Retail companies collect large volumes of transaction, product, household, coupon, campaign, promotion, and calendar data. However, this data is usually fragmented, noisy, and difficult to use directly for business decisions.

This project answers the following question:

> How can raw multi-source retail data be transformed into reliable, visual, and actionable insights for sales monitoring, customer targeting, campaign optimization, holiday planning, and product recommendation?

---

## 3. Main Contributions

The project contribution is not only building dashboards. It provides an integrated retail intelligence pipeline that includes:

1. A complete Azure PostgreSQL retail data warehouse.
2. Conservative data cleaning that preserves business records while flagging issues.
3. Fact and dimension modeling for Power BI and data mining.
4. Data quality validation views for warehouse trust and debugging.
5. Power BI dashboards for sales, products, customers, campaigns, coupons, holidays, and validation.
6. RFM-based customer segmentation using K-Means, DBSCAN, and Hierarchical Clustering.
7. Market basket analysis using Apriori, FP-Growth, and ECLAT.
8. Algorithm comparison using rule quality, recommendation quality, runtime, and memory usage.
9. Holiday-aware retail behavior analysis using an external U.S. Federal Holidays dataset.
10. A recommendation prototype that suggests products based on association rules.

---

## 4. Technology Stack

| Area | Tools |
|---|---|
| Programming | Python |
| Database | Azure PostgreSQL |
| Data Modeling | Star / Galaxy Schema |
| ETL | Python, SQL, SQLAlchemy |
| BI and Reporting | Power BI |
| Data Mining | Scikit-learn, mlxtend / custom association mining scripts |
| Customer Segmentation | K-Means, DBSCAN, Hierarchical Clustering |
| Market Basket Analysis | Apriori, FP-Growth, ECLAT |
| Prototype | Streamlit |
| Version Control | Git, GitHub |

---

## 5. Data Sources

The project uses the **Dunnhumby Complete Journey** dataset because it provides a richer retail environment than the earlier dataset options. It supports transactions, products, households, campaigns, coupons, redemptions, and promotions.

An external **U.S. Federal Holidays** dataset is also integrated to support holiday and event impact analysis.

### Main Dataset Files

```text
basket_items_for_mba.csv
coupon_redemptions_clean.csv
campaigns_clean.csv
coupons_clean.csv
demographics_clean.csv
campaign_descriptions_clean.csv
products_clean.csv
promotions_clean.csv
transactions_clean.csv
```

Large CSV files are not committed to GitHub. They should be stored locally or in Google Drive / cloud storage.

Default data path used during development:

```text
/content/drive/MyDrive/complete_journey_data/preprocessed
```

---

## 6. End-to-End Pipeline

```text
Raw Retail CSV Files + Holiday Dataset
        ↓
Python Cleaning and Preprocessing
        ↓
Azure PostgreSQL Staging Tables
        ↓
Dimensions, Facts, and Validation Views
        ↓
Power BI Dashboards
        ↓
Customer Segmentation + Market Basket Analysis
        ↓
Recommendation Prototype
```

### Pipeline Steps

1. Collect and organize Complete Journey and holiday datasets.
2. Clean and preprocess raw CSV files.
3. Load cleaned data into Azure PostgreSQL staging tables using chunk loading.
4. Build dimensions and facts using SQL and Python ETL scripts.
5. Create validation and analytical views.
6. Connect Power BI to Azure PostgreSQL.
7. Build dashboard pages and KPI measures.
8. Run customer segmentation and association rule mining.
9. Export mining outputs to CSV for reporting and prototype integration.
10. Build a shopping recommendation prototype based on association rules.

---

## 7. Data Cleaning Strategy

The cleaning strategy is conservative. We avoid deleting transaction records unless there is a strong reason, because deleting sales rows can damage business analysis.

| Issue | Decision | Reason |
|---|---|---|
| Coupon duplicates | Removed 4,872 exact duplicate rows | Duplicates can inflate joins and bias coupon analysis |
| Invalid quantity values | Kept and flagged `quantity <= 0` records | They may represent returns, corrections, or special operations |
| Missing product / household references | Kept transaction rows and mapped missing references to unknown dimensions when needed | Deleting transactions can damage sales analysis |
| Outliers in sales, quantity, retail discount, and coupon discount | Detected using IQR, flagged, and capped columns were added | High values may reflect real bulk purchases or strong discounts |
| Rare coupon usage | No oversampling was applied | Oversampling would distort support, confidence, basket frequency, and recommendation results |
| Dates | Standardized for date dimension, campaign periods, and holiday matching | Time-based analysis requires reliable date fields |

---

## 8. Data Warehouse Design

Database platform:

```text
Azure PostgreSQL
```

Main schema:

```text
retail_dw
```

The warehouse follows a star / galaxy-inspired schema. Facts store measurable events, while dimensions provide descriptive business context.

### Naming Convention

```text
stg_   staging tables
dim_   dimension tables
fact_  fact tables
vw_    validation or analytical views
```

### 8.1 Staging Tables

```text
retail_dw.stg_transactions
retail_dw.stg_products
retail_dw.stg_promotions
retail_dw.stg_holidays
retail_dw.stg_demographics
retail_dw.stg_coupons
retail_dw.stg_coupon_redemptions
retail_dw.stg_campaigns
retail_dw.stg_campaign_descriptions
retail_dw.stg_basket_items_for_mba
```

Staging tables are used for loading and validation. They should not be used directly in final Power BI visuals unless debugging is needed.

### 8.2 Dimension Tables

```text
retail_dw.dim_date
retail_dw.dim_product
retail_dw.dim_household
retail_dw.dim_store
retail_dw.dim_campaign
retail_dw.dim_coupon
retail_dw.dim_holiday
```

Each dimension uses a surrogate key. Unknown rows are included where needed to avoid losing fact rows when references are missing.

Example:

```text
product_key = warehouse surrogate key
product_id  = original dataset product identifier
```

### 8.3 Fact Tables

```text
retail_dw.fact_transaction_item
retail_dw.fact_coupon_redemption
retail_dw.fact_campaign_participation
retail_dw.fact_product_promotion
```

#### fact_transaction_item

Main grain:

```text
One row = one product purchased inside one basket by one household at one store on a transaction date.
```

This fact supports:

- Sales analysis
- Basket analysis
- Product analysis
- Discount analysis
- Coupon usage analysis
- Customer analysis
- Holiday impact analysis

Important columns include original and capped values for quantity, sales value, retail discount, and coupon discount. This keeps traceability while allowing robust reporting.

#### fact_coupon_redemption

Main grain:

```text
One row = one coupon redeemed by one household in one campaign/date.
```

#### fact_campaign_participation

Main grain:

```text
One row = one household participating in one campaign.
```

#### fact_product_promotion

Main grain:

```text
One row = one product promoted in one store during one week.
```

---

## 9. Data Quality Validation

Validation was added to ensure that Power BI and mining scripts use trusted warehouse data.

### Validation Views

```text
retail_dw.vw_table_row_counts
retail_dw.vw_data_quality_summary
```

### Key Validation Results

| Validation Item | Result |
|---|---:|
| `fact_transaction_item` row count | 1,469,307 |
| `stg_basket_items_for_mba` row count | 1,469,307 |
| `dim_product` row count | 92,349 |
| Unique baskets for market basket analysis | 155,848 |
| Unique products | 68,509 |
| Null `basket_id` | 0 |
| Null `product_id` | 0 |
| Duplicate `basket_id + product_id` pairs | 0 |
| Unmatched `product_key` references | 0 |
| Unmatched `product_id` references | 0 |
| Unknown `product_key` rows | 0 |

### Important Fixes Applied

#### Campaign Duration Fix

`duration_days` was calculated using `end_date - start_date` for campaigns with valid dates.

```sql
UPDATE retail_dw.dim_campaign
SET duration_days = end_date - start_date
WHERE start_date IS NOT NULL
  AND end_date IS NOT NULL
  AND duration_days IS NULL;
```

#### Holiday Date Fix

Holiday text dates were mapped to real 2017 dates so the holiday dimension can join correctly with the date dimension and Power BI can analyze holiday impact.

---

## 10. Power BI Dashboards

Power BI connects to Azure PostgreSQL and uses only final facts, dimensions, and validation views. Staging tables are excluded from final visuals.

### Tables to Keep in Power BI

```text
retail_dw_dim_date
retail_dw_dim_product
retail_dw_dim_household
retail_dw_dim_store
retail_dw_dim_campaign
retail_dw_dim_coupon
retail_dw_dim_holiday

retail_dw_fact_transaction_item
retail_dw_fact_coupon_redemption
retail_dw_fact_campaign_participation
retail_dw_fact_product_promotion

retail_dw_vw_table_row_counts
retail_dw_vw_data_quality_summary
```

### Dashboard Pages

| Page | Purpose | Example KPIs / Visuals |
|---|---|---|
| Executive Overview | High-level retail snapshot | Total Sales, Total Baskets, Average Basket Value, Active Households, Coupon Usage Rate |
| Sales and Product Performance | Department and product analysis | Products Sold, Sales by Department, Top Categories, Treemap, Moving Average |
| Customer Segmentation | Behavioral customer grouping | Customer Count, VIP, Active Shoppers, Churned, RFM scatter and profile table |
| Campaign, Coupon, and Promotion Analysis | Marketing performance | Campaign participation, coupon redemptions, discount analysis, monthly redemptions |
| Holiday and Event Impact | Holiday-aware retail behavior | Holiday Sales, Non-Holiday Sales, Holiday Sales %, Uplift %, Sales by Holiday |
| Data Quality / DWH Validation | Warehouse trust and validation | Row counts, issue counts, passed/failed checks |

### Recommended Power BI Relationships

Use a star schema with single-direction filtering from dimensions to facts.

```text
dim_date.date_key           → fact_transaction_item.date_key
dim_product.product_key     → fact_transaction_item.product_key
dim_household.household_key → fact_transaction_item.household_key
dim_store.store_key         → fact_transaction_item.store_key
```

Coupon redemption:

```text
dim_coupon.coupon_key       → fact_coupon_redemption.coupon_key
dim_household.household_key → fact_coupon_redemption.household_key
dim_campaign.campaign_key   → fact_coupon_redemption.campaign_key
dim_date.date_key           → fact_coupon_redemption.date_key
```

Campaign participation:

```text
dim_campaign.campaign_key   → fact_campaign_participation.campaign_key
dim_household.household_key → fact_campaign_participation.household_key
```

Product promotion:

```text
dim_product.product_key → fact_product_promotion.product_key
dim_store.store_key     → fact_product_promotion.store_key
dim_date.date_key       → fact_product_promotion.date_key
```

Holiday relationship:

```text
dim_holiday.holiday_date → dim_date.full_date
```

If Power BI creates ambiguity, keep holiday fields inside `dim_date` or use `dim_holiday` as a descriptive lookup table.

---

## 11. Customer Segmentation

Customer segmentation was implemented using **RFM analysis**:

- **Recency:** How recently the household purchased
- **Frequency:** How often the household purchased
- **Monetary:** How much the household spent

Three clustering methods were compared:

| Method | Clusters | Silhouette Score | Notes |
|---|---:|---:|---|
| K-Means | 2 | 0.656 | Clean result, but mainly separates Active vs Churned customers |
| DBSCAN | 3 | 0.758 | Selected final model; discovers VIP outliers automatically |
| Hierarchical Clustering | 3 | Baseline comparison | Used to validate segment structure |

### Final Selected Model

```text
DBSCAN
```

DBSCAN was selected because it achieved the strongest silhouette score and identified VIP customers without manually specifying the number of clusters.

### Final Segments

| Segment | Recency | Frequency | Monetary | Size |
|---|---:|---:|---:|---:|
| Active Shoppers | 22 days | 103 baskets/year | $3,080 avg | 2,431 (97%) |
| VIP | 83 days | 476 baskets/year | $10,304 avg | 55 (2.2%) |
| Churned | 544 days | 4 baskets/year | $163 avg | 14 (0.6%) |

### Business Actions

| Segment | Recommended Action |
|---|---|
| VIP | Launch loyalty program, early access, personalized offers, and high-priority retention |
| Active Shoppers | Use personalized promotions on top categories to increase basket size |
| Churned | Run win-back campaigns using coupons based on last known purchase categories |

---

## 12. Market Basket Analysis

Market basket analysis was applied to discover category-level co-purchase relationships and support cross-selling recommendations.

### Algorithms Compared

```text
Apriori
FP-Growth
ECLAT
```

### Input After Filtering and Train/Test Split

| Item | Value |
|---|---:|
| Total basket-category rows | 1,078,691 |
| Total baskets | 155,691 |
| Product-category items | 303 |
| Train baskets | 124,418 |
| Test baskets | 31,273 |
| Train categories after rare-item filter | 301 |
| Train basket-item rows | 860,725 |

### Evaluation Metrics

| Metric | Meaning |
|---|---|
| Support | Fraction of baskets containing the itemset |
| Confidence | Probability of consequent given antecedent |
| Lift | Association strength compared with random chance |
| Precision@5 | Fraction of top-5 recommendations that appear in the hidden part of the test basket |
| Recall@5 | Fraction of hidden basket items captured by top-5 recommendations |
| Hit Rate@5 | Fraction of test baskets with at least one correct top-5 recommendation |
| Coverage | Share of unique test items ever recommended |
| Runtime | Execution time in seconds |
| Memory | Peak memory usage in MB |

### Accepted Thresholds

The adaptive search accepted the strictest threshold combination that produced an interpretable rule count:

```text
support    = 0.010
confidence = 0.60
lift       = 1.50
rules      = 969
```

The next looser threshold generated 5,983 rules, which was above the accepted interpretability band.

### Final Accepted Algorithm Ranking

| Algorithm | Support | Confidence | Lift | Rules | Avg Confidence | Avg Lift | Max Lift | Precision@5 | Recall@5 | Hit Rate@5 | Coverage | Quality | Runtime | Memory |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Apriori | 0.010 | 0.60 | 1.50 | 969 | 0.6698 | 3.1204 | 12.1518 | 0.166 | 0.048 | 0.246 | 0.027 | 0.381 | 7.18s | 3.45 MB |
| FP-Growth | 0.010 | 0.60 | 1.50 | 969 | 0.6698 | 3.1204 | 12.1518 | 0.166 | 0.048 | 0.246 | 0.027 | 0.381 | 5.02s | 161.18 MB |
| ECLAT | 0.010 | 0.60 | 1.50 | 969 | 0.6698 | 3.1204 | 12.1518 | 0.166 | 0.048 | 0.246 | 0.027 | 0.381 | 3.47s | 51.52 MB |

### Final Interpretation

All three algorithms produced identical rule quality at the accepted threshold, so the selection depends on deployment constraints:

- **Best runtime:** ECLAT, 3.47 seconds
- **Lowest memory usage:** Apriori, 3.45 MB
- **Best rule quality:** Tie between Apriori, FP-Growth, and ECLAT
- **Recommended for interactive prototype:** ECLAT
- **Recommended for memory-constrained runs:** Apriori

At the accepted threshold, the recommender achieved:

```text
precision@5 = 0.166
recall@5    = 0.048
hit_rate@5  = 0.246
coverage    = 0.027
```

In business terms, around one in four test baskets received at least one correct recommendation in the top five suggestions.

---

## 13. Recommendation Prototype

The project includes an Amazon-like prototype concept where a user browses products, adds items to a cart, and receives recommendations generated from association rules.

### Prototype Features

| Feature | Description |
|---|---|
| Product Grid | Displays product cards similar to an e-commerce store |
| Search and Filters | Allows filtering by department, category, or product type |
| Cart | User adds, removes, or clears cart items |
| Recommended for Your Cart | Uses rules where antecedents match current cart items |
| Rule Explanation | Shows support, confidence, lift, algorithm, and recommendation reason |
| Data Source | Reads exported association rule CSV files in the first version |

Recommended scoring formula:

```text
score = 0.45 × normalized_lift + 0.35 × normalized_confidence + 0.20 × normalized_support
```

---

## 14. Project Structure

Recommended repository structure:

```text
Retail-Intelligence-DWH/
│
├── data/                         # Local only; not committed
│   └── preprocessed/
│
├── sql/
│   ├── schema/                   # Create schema, dimensions, facts
│   ├── views/                    # Analytical and validation views
│   ├── indexes/                  # Performance indexes
│   └── validation/               # Validation queries
│
├── scripts/
│   ├── load_staging.py           # Load cleaned CSVs to staging tables
│   ├── load_dimensions_and_facts.py
│   ├── create_analytics_views.py
│   ├── run_customer_segmentation.py
│   ├── run_market_basket_analysis.py
│   └── db_utils.py
│
├── notebooks/
│   ├── eda/
│   ├── segmentation/
│   └── market_basket_analysis/
│
├── outputs/
│   ├── association_rules_results.csv
│   ├── algorithm_comparison.csv
│   ├── customer_segments.csv
│   └── product_recommendations.csv
│
├── prototype/
│   └── streamlit_app.py
│
├── docs/
│   └── Retail_Intelligence_Documentation.docx
│
├── .env.example
├── requirements.txt
└── README.md
```

---

## 15. Environment Variables

Do not commit the real `.env` file. Use `.env.example` only.

```env
Azure_DB_HOST=your-server-name.postgres.database.azure.com
Azure_DB_PORT=5432
Azure_DB_NAME=postgres
Azure_DB_USER=your_user
Azure_DB_PASSWORD=your_password

ETL_SCHEMA=retail_dw
DATA_DIR=/content/drive/MyDrive/complete_journey_data/preprocessed
ETL_CHUNKSIZE=100000

FORCE_RELOAD_STAGING=false
FORCE_RELOAD_FACT=false
```

---

## 16. How to Run

### 16.1 Create Environment

```bash
python -m venv .venv
source .venv/bin/activate      # Linux / Mac
# .venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 16.2 Configure Environment

Create a `.env` file based on `.env.example` and add the Azure PostgreSQL connection details.

### 16.3 Load Staging Tables

```bash
python scripts/load_staging.py
```

### 16.4 Build Dimensions and Facts

```bash
python scripts/load_dimensions_and_facts.py
```

### 16.5 Create Validation and Analytical Views

```bash
python scripts/create_analytics_views.py
```

### 16.6 Run Customer Segmentation

```bash
python scripts/run_customer_segmentation.py
```

Expected output:

```text
outputs/customer_segments.csv
outputs/customer_segmentation_comparison.csv
```

### 16.7 Run Market Basket Analysis

```bash
python scripts/run_market_basket_analysis.py
```

Expected output:

```text
outputs/association_rules_results.csv
outputs/algorithm_comparison.csv
outputs/product_recommendations.csv
```

### 16.8 Run Recommendation Prototype

```bash
streamlit run prototype/streamlit_app.py
```

---

## 17. Project Status

| Component | Status |
|---|---|
| Data preprocessing | Completed |
| Azure PostgreSQL staging load | Completed |
| Warehouse schema | Completed |
| Dimensions and facts | Completed |
| Validation views | Completed |
| Campaign duration fix | Completed |
| Holiday date fix | Completed |
| Power BI dashboards | Completed / refined |
| Customer segmentation | Completed |
| Market basket analysis | Completed |
| Algorithm comparison | Completed |
| Recommendation prototype | Prototype prepared / integration-ready |
| Research paper mapping | Prepared |

---

## 18. Team

| Name | ID |
|---|---:|
| Mohamed Goma | 221001823 |
| Abdullah Yasser | 221001008 |
| Mohamed Khaled | 221000741 |
| Mohamed Saleh | 221001519 |
| Mahitab Ayman | 212002434 |

---

## 19. Supervisor

**Dr. Shaimaa Mohamed**

Institution: **Nile University**  
Department: **Department of Computer Science**

---

## 20. References

1. R. Agrawal, T. Imielinski, and A. Swami, "Mining Association Rules Between Sets of Items in Large Databases," ACM SIGMOD, 1993.
2. J. Han, J. Pei, and Y. Yin, "Mining Frequent Patterns without Candidate Generation," ACM SIGMOD, 2000.
3. J. Han, M. Kamber, and J. Pei, *Data Mining: Concepts and Techniques*, 3rd ed., Morgan Kaufmann, 2011.
4. R. Kimball and M. Ross, *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling*, 3rd ed., Wiley, 2013.
5. M. J. Zaki, "Scalable Algorithms for Association Mining," IEEE Transactions on Knowledge and Data Engineering, 2000.
6. PostgreSQL Global Development Group, PostgreSQL Documentation.
7. Microsoft, Power BI Documentation.
8. F. Pedregosa et al., "Scikit-learn: Machine Learning in Python," Journal of Machine Learning Research, 2011.
