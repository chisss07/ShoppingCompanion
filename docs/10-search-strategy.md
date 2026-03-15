# Shopping Companion: Product Search & Data Sourcing Strategy

**Document Version:** 1.0
**Last Updated:** March 2026
**Status:** Design Specification

---

## Executive Summary

This document outlines the complete search and data sourcing strategy for the Shopping Companion AI app. The system will aggregate product pricing and availability data from multiple reputable sources, applying intelligent product matching, reputation scoring, and freshness management to deliver accurate price comparisons with confidence metrics.

**Key Objectives:**
- Compare prices across minimum 3 verified sources per product
- Achieve >95% product matching accuracy
- Provide real-time price data with transparent source attribution
- Filter out counterfeit/unreliable sellers automatically
- Enable user trust through reputation and freshness signals

---

## 1. Multi-Source Search Architecture

### 1.1 Hierarchical Source Strategy

The Shopping Companion uses a three-tiered source integration model, with automatic fallback and data consolidation:

```
User Query
    ↓
[Tier 1: Official APIs] ← Primary (fastest, most reliable)
    ↓
[Tier 2: Aggregator APIs] ← Secondary (broader coverage)
    ↓
[Tier 3: Web Scraping] ← Tertiary (fallback only)
    ↓
Product Matching & Deduplication
    ↓
Ranking & Reputation Scoring
    ↓
Result Presentation with Source Attribution
```

### 1.2 Concurrent vs Sequential Search

**Strategy:**
- Execute Tier 1 API calls concurrently (parallel) with 2-second timeout
- If Tier 1 yields <3 sources with acceptable results, trigger Tier 2 in parallel
- Tier 3 scraping triggers only if <2 sources provide valid data
- Total response target: <3 seconds for fresh results, <500ms for cached

**Implementation Approach:**
```
Query arrives
  └─ Check cache (TTL-aware, source-specific)
  └─ If miss or needs refresh:
      ├─ Parallel: Amazon Product Advertising API
      ├─ Parallel: Google Shopping (via SerpAPI)
      ├─ Parallel: Best Buy API
      ├─ Parallel: Walmart API
      ├─ Parallel: eBay Finding API
      │   Timeout: 2 seconds for all
      └─ If results < 3 sources:
          ├─ Parallel: PriceGrabber
          ├─ Parallel: CamelCamelCamel (Amazon history)
          └─ If still insufficient:
              └─ Responsible web scraping (see Section 3.3)
```

---

## 2. Data Sources (Prioritized)

### 2.1 Tier 1: Official APIs (Primary Integration)

#### A. Google Shopping API (via SerpAPI Recommendation)

**Why:** Most comprehensive retailer coverage, real-time indexing

**API Details:**
- **Provider:** Google Shopping Feed API or SerpAPI wrapper
- **Endpoint Category:** Product Search, Shopping Listings
- **Key Parameters:**
  - `q`: Product query string
  - `location`: User location (for local pricing/shipping)
  - `currency`: Currency conversion
  - `local`: Include local retailers
  
**Data Points Retrieved:**
- Product title (standard format)
- Price (current retail price)
- Retailer name and logo
- Product thumbnail/image
- Availability status (in stock/out of stock/pre-order)
- Seller rating/reviews count
- Shipping cost/method (if available)
- URL to product listing
- UPC/GTIN (when available in feed)

**Integration Approach:**
```
Use SerpAPI Google Shopping endpoint:
  Request: https://api.serpapi.com/search
    Params: {
      engine: "google_shopping",
      q: [product_query],
      location: [user_location],
      gl: [country_code],
      hl: [language_code]
    }
  
  Response includes:
    - shopping_results[] (20-50 items)
    - Each item: title, link, price, source, rating, reviews
```

**Rate Limits:** 100 requests/month (free tier); paid plans available
**Latency:** 500-800ms average
**Data Freshness:** 1-24 hours (Google's indexing frequency)

---

#### B. Amazon Product Advertising API (PA-API v5)

**Why:** Direct access to world's largest e-commerce platform

**API Details:**
- **Service:** AWS Product Advertising API v5
- **Authentication:** AWS Signature v4
- **Key Operations:**
  - `SearchItems`: Product search by query
  - `GetItems`: Detailed product data by ASIN
  - `GetVariations`: Variant/model alternatives
  
**Data Points Retrieved:**
- ASIN (Amazon Standard Identification Number)
- Product title and description
- Current price and list price
- Star rating and review count
- Availability (in stock/out of stock)
- Prime eligibility
- Product images
- Product categories
- Related items/variations
- Item attributes (brand, color, size, etc.)

**Integration Approach:**
```
Endpoint: https://api.amazon.com/onca/xml
  Operation: ItemSearch or ItemLookup
  Required Parameters:
    - AWSAccessKeyId
    - AssociateTag (your Amazon Associates ID)
    - Operation: SearchItems
    - Keywords: [product_query]
    - SearchIndex: All (or specific category)
    - ResponseGroup: Medium,VariationAttributes
    
  Returns:
    - Items (10 results per page)
    - ASIN, Title, Price, Availability
    - Variations (alternative colors/sizes)
```

**Rate Limits:** 1 request per second (throttled), daily quota varies
**Latency:** 800-1200ms
**Data Freshness:** Real-time prices, inventory updates every 1-4 hours
**Monetization:** Requires Amazon Associates account + referral commission

---

#### C. Best Buy API

**Why:** Specialized electronics retailer with rich technical specs

**API Details:**
- **Base URL:** `https://api.bestbuy.com/v1/products`
- **Key Endpoints:**
  - `/products`: Search and list products
  - `/products/{id}`: Get detailed product info
  - `/products/{id}/reviews`: Get user reviews
  - `/products/{id}/buying-options`: Get seller/pricing options
  
**Data Points Retrieved:**
- SKU and manufacturer model number
- Current price and pricing history
- In-store/online availability by location
- Product specifications (detailed tech specs)
- Customer reviews and ratings
- Related/similar products
- Buying options (new/used/refurbished)
- Price tags with historical prices

**Integration Approach:**
```
Authentication: API Key in query string or header
Endpoint: https://api.bestbuy.com/v1/products
  Parameters:
    - search: [product_query]
    - format: json
    - sort: relevance.asc
    - pageSize: 25
    - apiKey: [your_key]
  
  Returns:
    - Product SKU, title, description
    - Current price, regular price, card member price
    - Availability (in stock, nearby, online)
    - Customer rating, review count
    - Product images and specs
```

**Rate Limits:** 5,000 requests/hour (generous)
**Latency:** 300-500ms
**Data Freshness:** Real-time inventory, hourly price updates
**Registration:** Free API key from Best Buy Developer Portal

---

#### D. Walmart API (Walmart Product Search API)

**Why:** Large retailer with significant market share, grocery integration

**API Details:**
- **Base URL:** `https://api.walmartapis.com/v3/products`
- **Key Endpoints:**
  - `/search`: Search products
  - `/[id]`: Get detailed product info
  - `/reviews`: Get reviews for a product
  
**Data Points Retrieved:**
- Walmart item ID and UPC
- Product title and description
- Current price (Walmart.com + Walmart stores)
- Availability (online/in-store by location)
- Customer ratings and reviews
- Related items
- Seller information (Walmart or 3rd party)
- Shipping info
- Images and videos

**Integration Approach:**
```
Authentication: OAuth 2.0 with client credentials
Endpoint: https://api.walmartapis.com/v3/products/search
  Headers:
    - Authorization: Bearer [access_token]
    - WM_CONSUMER.ID: [consumer_id]
    - WM_CONSUMER.INTIMACY: Confidential
    - WM_SEC.ACCESS_TOKEN: [access_token]
    - WM_SVC.NAME: Walmart Product API
    - WM_QOS.CORRELATION_ID: [uuid]
  
  Parameters:
    - query: [product_query]
    - category: [optional_category_id]
    - sort: relevance
    - limit: 25
    - offset: 0
  
  Returns:
    - Items array with:
      - Item ID, UPC, name, description
      - Sale price, original price, currency
      - Availability, seller type
      - Product image URLs
```

**Rate Limits:** 5,000 requests/hour
**Latency:** 400-600ms
**Data Freshness:** Real-time prices, inventory updates every 1-6 hours
**Registration:** Requires Walmart Developer Account + business approval

---

#### E. eBay Finding API (or Browse API)

**Why:** Access to used/refurbished items and alternative sellers

**API Details:**
- **Newer Option:** eBay Browse API (REST-based)
- **Legacy Option:** eBay Finding API (XML-based)
- **Key Endpoints:**
  - `/item_summary/search`: Search items
  - `/item/{item_id}`: Get item details
  
**Data Points Retrieved:**
- Item ID and UPC
- Product title and description
- Current price (auction/fixed price)
- Item condition (new/used/refurbished)
- Seller feedback score and percentage
- Shipping cost and delivery time
- Item location
- Seller info
- Images

**Integration Approach:**
```
Endpoint: https://api.ebay.com/buy/browse/v1/item_summary/search
  Headers:
    - Authorization: Bearer [oauth_token]
    - X-EBAY-C-MARKETPLACE-ID: EBAY_US (or other country)
  
  Parameters:
    - q: [product_query]
    - limit: 50
    - category_ids: [optional]
    - filter: conditions:[{filter: NEW}] (optional)
    - sort: newlyListed
  
  Returns:
    - itemSummaries array with:
      - Item ID, title, description, image
      - Price (with currency), shipping cost
      - Condition, seller feedback
      - Delivery options
```

**Rate Limits:** 5,000 calls/day (per endpoint)
**Latency:** 600-900ms
**Data Freshness:** Real-time auction data, 10-minute cache acceptable
**Registration:** eBay Developer Account with OAuth credentials

---

### 2.2 Tier 2: Aggregator APIs (Secondary Integration)

#### A. PriceGrabber API

**Why:** Pre-aggregated merchant data, reduced API calls

**API Details:**
- **Base URL:** `https://api.pricegrabber.com/` (varies by region)
- **Purpose:** Aggregates prices from 1000+ merchants
- **Data Available:**
  - Merchant prices for product
  - Merchant rating and reviews
  - Product specifications
  - Historical price data
  - Availability across merchants

**Integration Approach:**
```
Authenticate with API key
Search endpoint: /search
  Parameters:
    - keyword: [product_query]
    - page: [page_number]
    - sort_by: price/rating/popularity
  
  Returns:
    - Products with merchant prices
    - Each merchant: name, price, rating, link
    - Product ID for detailed lookups
```

**Advantages:**
- Single API call yields 20+ merchants
- Merchant reputation pre-calculated
- Good for "breadth" searches

**Disadvantages:**
- Lower data freshness (30-120 minutes delay)
- Limited to supported product categories

---

#### B. CamelCamelCamel API (Amazon Price History)

**Why:** Track Amazon price fluctuations, identify price drops

**API Details:**
- **Base URL:** `https://camelcamelcamel.com/`
- **Purpose:** Amazon price history tracker
- **Data Available:**
  - ASIN to price history mapping
  - Historical price charts (90/180/365 day views)
  - Price drop alerts
  - Product availability history

**Integration Approach:**
```
Access via direct URL pattern:
  https://camelcamelcamel.com/[ASIN]/price-history

Or use unofficial API endpoint:
  https://camelcamelcamel.com/api/v2/graph?asin=[ASIN]
  Returns:
    - Date-stamped prices
    - Price ranges (min/max/current)
    - Availability indicators

Typical response:
  {
    "asin": "B0123456789",
    "title": "Product Name",
    "price": 29.99,
    "currency": "USD",
    "history": [
      {"date": "2026-03-15", "price": 29.99, "availability": "In Stock"},
      {"date": "2026-03-14", "price": 34.99, "availability": "In Stock"},
      {"date": "2026-03-10", "price": 24.99, "availability": "In Stock"}
    ]
  }
```

**Use Case:** Supplement Amazon data with price trend analysis
**Refresh Rate:** Daily (suitable for historical tracking)

---

### 2.3 Tier 3: Web Scraping (Fallback Strategy)

**Scope:** Only when Tier 1 & 2 fail to return minimum 3 sources

**Target Retailers (if scraped):**
- Target (target.com) - Popular consumer goods
- Costco (costco.com) - Bulk items, member exclusives
- Home Depot (homedepot.com) - Tools/home improvement
- Newegg (newegg.com) - Electronics
- Etsy (etsy.com) - Unique/specialty items
- Manufacturer direct sites (for premium products)

#### 2.3.1 Responsible Scraping Framework

**Robots.txt Compliance:**
```
Before scraping ANY domain, fetch and parse robots.txt:
  
  GET /robots.txt
  
  Check:
    1. Is /products or equivalent path blocked? → Skip scraping
    2. What is the Crawl-delay or Request-rate?
       Default: 1 request per 10 seconds minimum
    3. Is User-Agent "*" unrestricted? → OK to proceed
    4. Site-specific rules (Disallow, Allow)
  
  Example robots.txt rules:
    User-agent: *
    Crawl-delay: 5          → Wait 5 seconds between requests
    Request-rate: 2/10s    → Max 2 requests per 10 seconds
    Disallow: /admin
    Disallow: /search      → Don't scrape search results
    Disallow: /cart
    Allow: /products       → OK to scrape product pages
```

**Rate Limiting Implementation:**
```
Per-domain request queue:
  ├─ target.com: Max 1 request per 10 seconds
  ├─ homedepot.com: Max 1 request per 8 seconds  
  ├─ costco.com: Max 1 request per 15 seconds
  └─ newegg.com: Max 2 requests per 10 seconds
  
  Implementation:
    - Maintain per-domain timestamp of last request
    - Before scraping, calculate required wait time
    - Use exponential backoff if receiving 429 (Too Many Requests)
    - Implement user-agent rotation (but disclose bot nature)
```

**User-Agent Declaration:**
```
HTTP Header:
  User-Agent: ShoppingCompanion/1.0 (+https://shoppingcompanion.app/bot)

This identifies the scraper as a bot and provides contact info.
Avoids deceptive user-agent masquerading.
```

**Data Extraction Strategy:**
```
Product Page Scraping:
  1. Fetch HTML (with timeout: 10 seconds)
  2. Parse DOM using CSS selectors or XPath
  3. Extract:
     - Product title (h1, meta[property="og:title"])
     - Price (script[type="application/ld+json"] for structured data)
     - Availability (span.availability, button.add-to-cart disabled)
     - Product image (img[alt], meta[property="og:image"])
     - UPC (meta[name="sku"], structured data)
  4. Store with:
     - scraped_timestamp
     - source_url
     - confidence_score (0.7-0.95 for scraped data)
```

**Error Handling & Backup:**
```
If scrape fails:
  - Log error with timestamp
  - Retry once after 30 seconds
  - If still fails, skip source (don't error entire request)
  - Fall back to Tier 1/2 results
  - Never return incomplete data to user
```

---

## 3. Query Optimization & Transformation

### 3.1 Query Normalization Pipeline

**Goal:** Transform natural user queries into effective search terms across diverse APIs

**Pipeline Steps:**

```
User Input: "Apple headphones with noise canceling under $100"
  ↓
[Step 1: Tokenization & Cleaning]
  Remove: stop words (with, the, a)
  Output: ["Apple", "headphones", "noise", "canceling", "under", "$100"]
  ↓
[Step 2: Entity Extraction]
  Brand: "Apple"
  Product Category: "headphones"
  Features: ["noise canceling"]
  Price Constraint: {"max": 100, "currency": "USD"}
  ↓
[Step 3: Query Variant Generation]
  Variant 1: "Apple headphones noise cancelling" (Tier 1 APIs)
  Variant 2: "Apple AirPods noise canceling" (brand expansion)
  Variant 3: "apple airpods pro" (exact model)
  Variant 4: "wireless earbuds noise cancellation $0-100" (Aggregator API)
  ↓
[Step 4: Source-Specific Formatting]
  Amazon: "Apple headphones noise cancellation" (SearchItems)
  Best Buy: search="Apple headphones" + filter: (price<100)
  eBay: "Apple headphones noise canceling" + condition:NEW
  Google Shopping: "Apple headphones noise canceling" + currency conversion
  ↓
[Step 5: Parallel Execution]
  All variants execute concurrently across appropriate sources
  ↓
[Step 6: Deduplication & Merging]
  Combine results from all variants
  Remove duplicate products
  Select best match scores (see Section 4)
```

### 3.2 Query Enhancement Techniques

**Synonym Expansion:**
```
Original query: "phone charger"
  Expand to synonyms:
    - "phone charger"
    - "smartphone charger"
    - "mobile charger"
    - "phone charging cable"
    - "USB-C charger" (if applicable)
    - "power adapter"

Search all variants, deduplicate results
```

**Model & Variant Detection:**
```
User input: "iPhone 15 Pro Max case"
  Extract entities:
    - Brand: "Apple"
    - Product line: "iPhone"
    - Model: "15 Pro Max"
    - Category: "case"
    - Variant specificity: HIGH
  
  Generate focused queries:
    1. "iPhone 15 Pro Max case" (exact match)
    2. "Apple iPhone 15 Pro case" (with brand)
    3. "iPhone 15 Pro Max protective case" (feature addition)
    4. "iPhone 15 Pro case" (fallback: older model)
```

**Category-Specific Optimization:**
```
Electronics category:
  - Prioritize: model number, specs
  - Add: compatible products
  - Example: "Dell XPS 13 (2025)" → search for "XPS 13 9340"

Clothing category:
  - Prioritize: size, color, fit
  - Add: material, style
  - Example: "blue jeans size 32" → search variations with colors

Home & Garden category:
  - Prioritize: dimensions, material
  - Add: color, finish
  - Example: "couch" → search "sectional sofa 90 inches gray"
```

### 3.3 Price Range Filtering

**Constraint Extraction:**
```
Input patterns:
  - "under $50" → max_price: 50
  - "$30 to $60" → min_price: 30, max_price: 60
  - "$100+" → min_price: 100
  - "cheap" → max_price: 50 (heuristic)
  - "luxury" → min_price: 500 (heuristic)

Apply post-search filtering:
  For each result:
    - Convert price to user's currency
    - Check: min_price <= result_price <= max_price
    - Filter out results outside range
    - Rank results closer to midpoint higher
```

---

## 4. Product Matching Algorithm

### 4.1 Multi-Level Matching Strategy

**Goal:** Identify when the same product appears in different sources with high confidence

**Matching Hierarchy (in priority order):**

```
Level 1: Universal Product Codes (HIGHEST CONFIDENCE)
  ├─ UPC match (12-digit)
  ├─ EAN match (13-digit)
  ├─ GTIN match (14-digit)
  ├─ ASIN match (10-digit, Amazon-specific)
  └─ Confidence: 99.5% (if source reliable)

Level 2: Manufacturer Model Numbers (HIGH CONFIDENCE)
  ├─ Exact model number match
  ├─ SKU match (retailer-specific)
  ├─ Manufacturer part number
  └─ Confidence: 97% (requires cross-verification)

Level 3: Fuzzy String Matching (MEDIUM CONFIDENCE)
  ├─ Levenshtein distance on product title
  ├─ Jaccard similarity on tokens
  ├─ Brand + model keyword overlap
  └─ Confidence: 75-90% (combined with other signals)

Level 4: Structural/Specification Matching (MEDIUM CONFIDENCE)
  ├─ Brand + price proximity ($5 range)
  ├─ Matching product dimensions
  ├─ Matching weight
  ├─ Matching key specs (RAM, storage, color)
  └─ Confidence: 70-85% (requires 3+ matching specs)

Level 5: Seller/Retailer Logic (LOW CONFIDENCE, FALLBACK)
  ├─ Same seller offering product variants
  ├─ Related item links
  └─ Confidence: 50-70% (use only if no other match)
```

### 4.2 UPC/EAN/GTIN Extraction & Matching

**Data Sources for Code Discovery:**

```
1. API Direct Extraction:
   - Amazon PA-API: Returns ASIN + product attributes
   - Best Buy API: Returns SKU + UPC in API response
   - Walmart API: Returns UPC directly
   - eBay API: May include item specifics with UPC

2. Structured Data (Web Scraping):
   - JSON-LD (script[type="application/ld+json"])
     Example:
       {
         "@context": "https://schema.org",
         "@type": "Product",
         "sku": "123456789",
         "gtin12": "123456789012",
         "gtin13": "1234567890123"
       }
   
   - Microdata (itemtype="https://schema.org/Product")
     Example: <span itemprop="gtin">123456789012</span>
   
   - Meta tags (less reliable)
     Example: <meta name="sku" content="123456789012">

3. HTML Parsing (fallback):
   - Look for patterns in page content
   - Search for "UPC:", "GTIN:", "SKU:" labels
   - Extract 12-14 digit sequences near product title

4. Barcode Databases:
   - Query public UPC databases (barcodable.com, upcdatabase.com)
   - Cache results locally for subsequent queries
```

**Matching Algorithm:**

```
function match_products(product_a, product_b) {
  
  // Level 1: Direct code matching
  if (product_a.upc && product_b.upc) {
    if (product_a.upc == product_b.upc) {
      return {match: true, confidence: 0.995, reason: "UPC match"}
    }
  }
  
  if (product_a.ean && product_b.ean) {
    if (product_a.ean == product_b.ean) {
      return {match: true, confidence: 0.995, reason: "EAN match"}
    }
  }
  
  if (product_a.gtin && product_b.gtin) {
    if (product_a.gtin == product_b.gtin) {
      return {match: true, confidence: 0.995, reason: "GTIN match"}
    }
  }
  
  // Level 2: Model number matching
  if (product_a.model_number && product_b.model_number) {
    if (product_a.model_number.lower() == product_b.model_number.lower()) {
      // Verify brand/category match (avoid false positives)
      if (product_a.brand == product_b.brand) {
        return {match: true, confidence: 0.97, reason: "Model match"}
      }
    }
  }
  
  // Level 3: Fuzzy matching
  title_distance = levenshtein_distance(
    product_a.title.lower(),
    product_b.title.lower()
  )
  max_distance = max(product_a.title.length, product_b.title.length) * 0.15
  
  if (title_distance <= max_distance) {
    // Additional verification
    brand_match = (product_a.brand.lower() == product_b.brand.lower())
    price_proximity = abs(product_a.price - product_b.price) <= 5.00
    
    if (brand_match && price_proximity) {
      confidence = 0.85 - (title_distance / max_distance) * 0.1
      return {match: true, confidence: confidence, reason: "Fuzzy match"}
    }
  }
  
  // Level 4: Spec matching
  matching_specs = 0
  for (spec in important_specs) {
    if (product_a[spec] == product_b[spec]) {
      matching_specs += 1
    }
  }
  
  if (matching_specs >= 3) {
    confidence = 0.70 + (matching_specs / total_specs) * 0.15
    return {match: true, confidence: confidence, reason: "Spec match"}
  }
  
  return {match: false, confidence: 0, reason: "No match found"}
}
```

**Matching Confidence Score Thresholds:**

```
≥ 0.95: Treat as same product (merge prices)
0.85 - 0.95: Same product, flag for manual review if prices differ >10%
0.70 - 0.85: Likely same, mention alternative models in results
< 0.70: Different products, list separately
```

---

### 4.3 Deduplication Process

**When multiple sources provide same product:**

```
Input: 5 results from different sources, 3 identified as same product
  - Amazon: iPhone 15 Pro Max, $999, A-listing-123
  - Best Buy: Apple iPhone 15 Pro Max, $999, SKU-456
  - Walmart: iPhone 15 Pro Max 256GB, $999, UPC-789
  - eBay: iPhone 15 Pro Max (New), $999, Item-999
  - Target: iPhone 15 Pro Max, $999.99, ID-555

Merge into single consolidated result:
  {
    "product_id": "iphone-15-pro-max-256gb",
    "canonical_title": "Apple iPhone 15 Pro Max 256GB",
    "upc": "123456789012",
    "best_price": 999.00,
    "price_by_source": [
      {"source": "Amazon", "price": 999.00, "url": "amazon.com/...", "timestamp": "2026-03-15T10:23:00Z"},
      {"source": "Best Buy", "price": 999.00, "url": "bestbuy.com/...", "timestamp": "2026-03-15T10:25:00Z"},
      {"source": "Walmart", "price": 999.00, "url": "walmart.com/...", "timestamp": "2026-03-15T10:22:00Z"},
      {"source": "eBay", "price": 999.00, "url": "ebay.com/...", "timestamp": "2026-03-15T10:28:00Z"},
      {"source": "Target", "price": 999.99, "url": "target.com/...", "timestamp": "2026-03-15T10:24:00Z"}
    ],
    "source_count": 5,
    "availability": {
      "in_stock": 4,
      "out_of_stock": 0,
      "pre_order": 1
    }
  }
```

---

## 5. Result Ranking Algorithm

### 5.1 Multi-Factor Ranking System

**Goal:** Present best value options first (not just lowest price)

**Ranking Factors:**

```
score = (
  price_score * 0.30 +           // Price value (inverted)
  source_reputation * 0.25 +     // Seller/source trustworthiness
  availability_score * 0.20 +    // In-stock, shipping speed
  freshness_score * 0.15 +       // How recent is the data
  match_confidence * 0.10        // How confident are we it's same product
)

Range: 0.0 (worst) to 1.0 (best)
Threshold: Only show results ≥ 0.55
```

### 5.2 Price Score Calculation

```
function price_score(product_prices) {
  median_price = calculate_median(product_prices)
  this_price = product_prices[0]
  
  // Penalize extreme prices (outliers)
  if (this_price < median_price * 0.85) {
    // Unusually cheap - may be counterfeit/damaged
    adjustment = 1.0 - (abs(this_price - median_price) / median_price) * 0.5
    base_score = 1.0 - (this_price / median_price)
  } else if (this_price > median_price * 1.15) {
    // Unusually expensive
    adjustment = 1.0 - (abs(this_price - median_price) / median_price) * 0.3
    base_score = 1.0 - (this_price / median_price)
  } else {
    // Within normal range
    base_score = 1.0 - (this_price / median_price)
    adjustment = 1.0
  }
  
  // Include shipping cost if available
  if (shipping_cost) {
    total_cost = this_price + shipping_cost
    base_score = 1.0 - (total_cost / (median_price + avg_shipping))
  }
  
  return base_score * adjustment  // Result: 0.0 to 1.0
}
```

### 5.3 Source Reputation Score

**Components:**

```
source_reputation = (
  seller_rating_normalized * 0.40 +
  return_policy_score * 0.25 +
  fraud_risk_score * 0.20 +
  longevity_score * 0.15
)

Calculation details:

1. Seller Rating (0.0-1.0):
   - Amazon: star_rating / 5.0 (4.5+ stars = 0.9+)
   - Best Buy: official retailer = 1.0
   - eBay: (feedback_score / 100) capped at 1.0
   - Walmart: official retailer = 0.95
   - Generic scraped seller: 0.70 (unless verified)

2. Return Policy Score (0.0-1.0):
   - 30+ days: 1.0
   - 15-30 days: 0.8
   - 7-14 days: 0.6
   - <7 days or none: 0.3

3. Fraud Risk Score (0.0-1.0):
   - Official retailer: 1.0
   - Verified 3rd party seller: 0.85
   - Unverified seller with history: 0.65
   - New seller or negative reviews: 0.4
   - Suspicious patterns: 0.1

4. Longevity Score (0.0-1.0):
   - Operating 10+ years: 1.0
   - 5-10 years: 0.9
   - 1-5 years: 0.75
   - <1 year: 0.5
```

**Red Flags That Lower Reputation (Automatic Penalties):**

```
Price significantly lower than others (>15% cheaper):
  → Apply -0.2 reputation penalty
  → Flag: "Unusually cheap, verify authenticity"

Seller has negative reviews mentioning:
  → Counterfeit, fake products: -0.3 reputation
  → Non-delivery or late shipping: -0.2 reputation
  → Item quality issues: -0.15 reputation

Seller operates from unexpected geography:
  → Expected: US-based retailer shipping from overseas: -0.1
  → Unexpected: Electronics seller from high-fraud region: -0.15

SSL/HTTPS not available:
  → Automatic: Don't display option

No contact information available:
  → -0.2 reputation penalty
```

### 5.4 Availability Score

```
function availability_score(product, user_location) {
  
  base_score = 0.0
  
  // In-stock status
  if (product.availability == "in_stock") {
    base_score = 1.0
  } else if (product.availability == "limited_stock") {
    base_score = 0.85
  } else if (product.availability == "pre_order") {
    base_score = 0.60  // Lower score for pre-order
  } else if (product.availability == "out_of_stock") {
    base_score = 0.0   // Don't show OOS products (unless explicitly requested)
    return base_score
  }
  
  // Shipping speed adjustment
  if (product.shipping_method) {
    if (product.shipping_method == "free_2day" || product.prime_eligible) {
      base_score += 0.15  (cap at 1.0)
    } else if (product.shipping_method == "free_standard_5_7day") {
      base_score += 0.05
    } else if (product.shipping_cost > 10) {
      base_score -= 0.1
    }
  }
  
  // Local availability bonus
  if (product.in_store_pickup || product.local_delivery) {
    base_score = min(1.0, base_score + 0.1)
  }
  
  return base_score  // 0.0 to 1.0
}
```

### 5.5 Freshness Score

```
function freshness_score(product, current_time) {
  
  last_updated = product.last_price_update
  age_minutes = (current_time - last_updated).total_seconds() / 60
  
  // Different freshness expectations per source
  freshness_max_age = {
    "Amazon": 120,       // 2 hours
    "Best Buy": 180,     // 3 hours
    "Walmart": 240,      // 4 hours
    "eBay": 60,          // 1 hour (auctions change frequently)
    "Google Shopping": 240,  // 4 hours
    "Scraped": 1440      // 24 hours (less reliable)
  }
  
  source = product.source
  max_age = freshness_max_age.get(source, 240)
  
  if (age_minutes < 30) {
    return 1.0  // Very fresh
  } else if (age_minutes < max_age) {
    return 1.0 - (age_minutes / max_age) * 0.3
  } else if (age_minutes < max_age * 2) {
    return 0.7 - (age_minutes / max_age) * 0.2
  } else {
    return 0.3  // Very stale data
  }
}
```

### 5.6 Match Confidence Score

```
Already calculated in Section 4.2

Used directly in ranking formula at 0.10 weight
Results with lower match confidence are ranked lower
(Helps bury potential false matches)
```

---

## 6. Alternative Model Detection

### 6.1 Model Genealogy Tracking

**Goal:** Identify newer, older, or variant models of what user searched for

**Data Sources for Model Information:**

```
1. Manufacturer Websites:
   - Apple: apple.com/iphone → current & previous models
   - Samsung: samsung.com → model lineup
   - Sony: sony.com → product families
   
2. Tech Spec Databases:
   - GSMarena.com (phones)
   - MacRumors Buyer's Guide (Apple)
   - DxOMark (cameras)
   - PCPartPicker (computers)

3. Wikipedia & Wikidata:
   - List of product models (e.g., "List of iPhone models")
   - Product lineage & release dates
   - Family relationships (base model → Pro → Max)

4. News & Review Sites:
   - AnandTech, The Verge, CNET
   - Product announcements, release dates
   - Discontinuation notices

5. Retailer Historical Data:
   - Store.apple.com "Discontinued" section
   - Best Buy search filters (year/generation)
```

### 6.2 Product Family Detection

```
When user searches for: "iPhone 14"

System identifies family tree:
  iPhone 14
    ├─ iPhone 14 (base)
    ├─ iPhone 14 Plus (newer variant, 2023)
    ├─ iPhone 14 Pro
    └─ iPhone 14 Pro Max
  
  Related previous generation:
    ├─ iPhone 13 (previous)
    └─ iPhone 13 Pro / Pro Max
  
  Related next generation:
    ├─ iPhone 15 (newer)
    └─ iPhone 15 Pro / Pro Max

Matching logic:
  Priority 1: Exact match (iPhone 14)
  Priority 2: Same family variant (iPhone 14 Plus)
  Priority 3: Previous generation (iPhone 13)
  Priority 4: Next generation (iPhone 15)
  Priority 5: Competitor alternatives (Samsung Galaxy S24)
```

### 6.3 Feature Comparison between Variants

**When displaying alternatives:**

```
Original query: "iPhone 14 Pro"
Main result: iPhone 14 Pro 256GB

Alternative options shown:
  1. iPhone 14 Pro Max (same generation, larger, more expensive)
     Differences: 
       - 6.7" vs 6.1" display
       - Same chip: A16 Bionic
       - Better zoom (12MP telephoto vs 12MP)
     Price premium: +$100
     
  2. iPhone 15 Pro (next generation)
     Differences:
       - Newer A17 Pro chip (+25% performance)
       - Better camera: 48MP main sensor
       - Improved video: ProRes codec support
       - USB-C (vs Lightning)
     Price: Same ($999)
     
  3. iPhone 13 Pro (previous generation)
     Differences:
       - Older A15 Bionic chip (-20% performance)
       - 12MP camera (vs 48MP)
       - Still good for most users
     Discount: -$200

Display format:
  {
    "original_product": {...},
    "alternatives": [
      {
        "product": {...},
        "relationship": "same_family_variant | newer_generation | older_generation | competitor",
        "key_differences": [
          {"feature": "Display Size", "original": "6.1\"", "alternative": "6.7\"", "significance": "notable"},
          {"feature": "Processor", "original": "A16 Bionic", "alternative": "A17 Pro", "significance": "major"}
        ],
        "price_difference": "+$100",
        "recommendation_reason": "Larger display and better zoom"
      }
    ]
  }
```

### 6.4 Successor/Newer Model Identification

**Automatic Detection Rules:**

```
1. Release Date Based:
   If (new_model.release_date > original.release_date)
   AND (time_since_release < 18_months)
   AND (same_brand AND same_category)
   → Flag as "Newer model" (not replacement if predecessor still sold)

2. Specification Based:
   If (new_model.performance > original.performance * 1.15)
   AND (new_model.features >= original.features)
   → Flag as "Successor model"

3. Manufacturer Messaging:
   If (manufacturer positions new_model as successor)
   AND (discontinued original model)
   → Flag as "Direct successor"

4. Market Position:
   If (new_model in same price tier as original)
   AND (new_model in same retailer placement as original)
   → Flag as "Direct replacement"

Example:
  User searched: "iPhone 13"
  
  Detection:
    - iPhone 14: Released Sept 2022 (newer)
    - iPhone 14 Pro: Released Sept 2022 (newer + pro variant)
    - iPhone 15: Released Sept 2023 (newer, not current successor if 14 still sold)
    
  Recommendation:
    Primary results: iPhone 13 (as requested)
    Alternative section: "Consider iPhone 14 (newer, $100 more)"
```

---

## 7. Reputation & Trust Scoring

### 7.1 Multi-Dimensional Trust Framework

```
Overall Trust Score = (
  source_authenticity * 0.25 +
  transaction_safety * 0.25 +
  product_authenticity * 0.25 +
  customer_satisfaction * 0.25
)

Range: 0.0 (do not show) to 1.0 (fully trusted)
Display threshold: ≥ 0.60
Recommend/highlight threshold: ≥ 0.85
```

### 7.2 Source Authenticity Scoring

**Verification Steps:**

```
1. Is this an official retailer?
   ✓ Owned by Amazon/Apple/Microsoft/Nike directly: 1.0
   ✓ Authorized distributor (verified via manufacturer): 0.95
   ✓ Major established retailer (20+ years): 0.90
   ✗ Third-party marketplace seller: 0.65-0.85
   ✗ Unknown seller: 0.40-0.60

2. Business verification:
   ✓ Registered business (check state records): +0.05
   ✓ Physical address available: +0.05
   ✓ Phone number with business hours: +0.05
   ✗ No contact info: -0.10
   ✗ "Fulfilled by Amazon" (but not Amazon account): +0.05

3. Website security:
   ✓ Valid SSL certificate: +0.05
   ✓ Certificate from major CA: +0.02
   ✗ Missing HTTPS: -0.20 (auto-exclude)
   ✗ Self-signed certificate: -0.15 (auto-exclude)

4. Domain age & registration:
   ✓ Domain registered 5+ years: +0.05
   ✓ Domain registered 2-5 years: +0.02
   ✗ Domain registered <6 months: -0.10
   ✗ Domain registered <3 months: -0.20 (auto-exclude for high-value items)

5. Company registration check:
   Query: UCC filings, BBB registration, state business records
   ✓ Legitimate registration found: +0.10
   ✗ Multiple failed searches: -0.10
```

### 7.3 Transaction Safety Scoring

**Payment Method Assessment:**

```
Scoring by payment option:

Credit Card / Debit Card:
  ✓ Merchant has fraud protection: 0.9
  ✓ Standard merchant category code: +0.05
  ✗ High-risk category code: -0.10

PayPal / Digital Wallet:
  ✓ PayPal Buyer Protection available: 0.95
  ✓ Apple Pay / Google Pay integration: +0.05

COD (Cash on Delivery):
  ✗ High fraud risk: -0.20

Cryptocurrency only:
  ✗ No fraud recovery: -0.40 (exclude)
```

**Return Policy Strength:**

```
30+ days full refund: 0.95
30+ days refund minus shipping: 0.85
15-29 days full refund: 0.80
7-14 days full refund: 0.60
<7 days or store credit only: 0.40
No returns stated: 0.0 (flag warning)
```

**Shipping Security:**

```
Tracked shipping with signature: 0.95
Tracked shipping: 0.90
Untracked: 0.50 (unless international)
Free shipping (no tracking): 0.40
```

**Total Transaction Safety Score:**

```
score = (
  payment_security * 0.40 +
  return_policy_strength * 0.40 +
  shipping_security * 0.20
)
```

### 7.4 Product Authenticity Detection

**Red Flags (Automatic Warnings):**

```
1. Price signals:
   - Price 20%+ below retail: FLAG "Verify authenticity"
   - Price below wholesale cost: FLAG "Likely counterfeit"
   - Extreme variance between sellers: FLAG "Investigate bulk"

2. Seller behavior signals:
   - Seller also selling suspicious items: FLAG
   - Seller operating from known counterfeit hub (e.g., specific regions): FLAG
   - Seller has negative reviews mentioning "fake" / "counterfeit": FLAG
   - Seller account created recently with high inventory: FLAG

3. Product presentation signals:
   - Product photos obviously copied from official source: FLAG
   - Product description copied verbatim (poor grammar): FLAG
   - Missing official product imagery: FLAG
   - No serial number visible in photos: FLAG

4. Packaging/delivery signals:
   - Unusual shipping origin (e.g., luxury brand from generic warehouse): FLAG
   - Packaging shows signs of tampering: FLAG (if visible in photos)
   - Seller history of repackaging items: FLAG

5. Specification mismatches:
   - Claimed specifications don't match official specs: FLAG
   - Missing hologram/security features: FLAG (luxury goods)
```

**Authenticity Scoring:**

```
function authenticity_score(seller, product, price) {
  
  score = 0.85  // Start with neutral-positive
  
  // Price analysis
  retail_price = product.official_msrp
  if (price < retail_price * 0.80) {
    score -= 0.15
  }
  
  if (price < retail_price * 0.50) {
    score -= 0.40
    flag_for_review = true
  }
  
  // Seller history
  if (seller.negative_reviews.includes("counterfeit")) {
    score = 0.10
    return score  // Auto-exclude
  }
  
  if (seller.negative_reviews.includes("fake")) {
    score -= 0.25
  }
  
  if (seller.account_age_days < 90) {
    score -= 0.10
  }
  
  // Geographic risk
  if (seller.location in high_counterfeit_regions) {
    score -= 0.15
  }
  
  // Official vs reseller
  if (seller.is_official_authorized_dealer) {
    score = min(1.0, score + 0.15)
  }
  
  return max(0.0, score)
}
```

### 7.5 Customer Satisfaction Metrics

**Data Collection:**

```
1. Seller ratings (normalized to 0-1 scale):
   - Amazon: seller_rating / 5.0
   - eBay: feedback_score / 100 (capped at 1.0)
   - Walmart: official seller = 1.0, 3P = varies
   - Best Buy: official = 1.0

2. Review analysis:
   - Count: reviews > 100: 1.0, 10-100: 0.7, <10: 0.4
   - Sentiment: positive/negative review ratio
   - Recency: recent reviews weighted higher
   - Relevance: reviews for same product category > general reviews

3. Return rate indicators (if accessible):
   - <2% return rate: 1.0
   - 2-5% return rate: 0.8
   - >5% return rate: 0.5

4. Complaint history:
   - Zero complaints in past year: +0.05
   - <5 complaints per 100 sales: neutral
   - >10 complaints per 100 sales: -0.15
```

**Calculation:**

```
function satisfaction_score(seller, product_category) {
  
  category_reviews = seller.reviews.filter(r => r.category == product_category)
  
  if (len(category_reviews) < 5) {
    // Insufficient data
    score = seller.overall_rating * 0.5
  } else {
    positive_ratio = count(r.rating >= 4) / len(category_reviews)
    review_count_score = min(1.0, len(category_reviews) / 100)
    
    score = positive_ratio * 0.7 + review_count_score * 0.3
  }
  
  // Recency boost
  recent_reviews = category_reviews.filter(age < 30_days)
  if (len(recent_reviews) > 0) {
    recent_positive_ratio = count(r.rating >= 4) / len(recent_reviews)
    if (recent_positive_ratio > positive_ratio) {
      score = min(1.0, score + 0.05)
    }
  }
  
  return score
}
```

### 7.6 Trust Score Display & Action Items

**UI Presentation:**

```
Trust Score ≥ 0.85: Green badge "Trusted Seller"
  Display: Name prominently, special indicator

Trust Score 0.70-0.85: Yellow badge "Established Seller"
  Display: Name normally, include brief note

Trust Score 0.60-0.70: Gray badge "Verify Details"
  Display: Name with caution indicator
  Additional info: Return policy, seller rating
  Show: "See seller reviews"

Trust Score < 0.60: Red badge "High Risk" or Hide
  Action: Hide from default results
  Option: "Show high-risk sellers" toggle (advanced)
  Display if shown: All verification info, "Buy with caution" warning
```

---

## 8. Freshness & Accuracy Strategy

### 8.1 Cache TTL (Time To Live) Policy

**Goal:** Balance data freshness with API quota and response time

```
Cache policy by source and product type:

Tier 1 APIs (Official):
┌─────────────────┬─────────────┬─────────────┐
│ Source          │ Product     │ Cache TTL   │
├─────────────────┼─────────────┼─────────────┤
│ Amazon          │ Electronics │ 2 hours     │
│ Amazon          │ Books       │ 6 hours     │
│ Amazon          │ Groceries   │ 1 hour      │
│ Best Buy        │ Electronics │ 3 hours     │
│ Best Buy        │ Other       │ 6 hours     │
│ Walmart         │ All         │ 4 hours     │
│ eBay            │ All         │ 1 hour      │
│ Google Shopping │ All         │ 4 hours     │
└─────────────────┴─────────────┴─────────────┘

Tier 2 APIs (Aggregators):
│ PriceGrabber    │ All         │ 2 hours     │
│ CamelCamelCamel │ Amazon hist │ 1 day       │

Tier 3 (Scraped):
│ Scraped         │ All         │ 24 hours    │
```

**Cache Key Structure:**

```
cache_key = hash(source + query + location + currency + user_preferences)

Example:
  amazon_iphone_us_usd_hash_a1b2c3 → cached_data
  bestbuy_iphone_us_usd_hash_a1b2c3 → cached_data
  ebay_iphone_us_usd_hash_d4e5f6 → cached_data
```

### 8.2 Stale Data Indicators

**Automatic Warnings:**

```
If (current_time - last_updated) > cache_ttl:
  - Mark data as "Last updated X hours ago"
  - Flag prices as potentially outdated
  - Suggest user "Refresh for latest prices"
  - Lower freshness_score in ranking algorithm

Visual treatment:
  ✓ Fresh data (< 30 min old): Green indicator "Updated now"
  ⚠ Aging data (30 min - 2 hrs): Yellow "Updated 1 hour ago"
  ⚠ Old data (2-8 hrs): Orange "Updated 4 hours ago"
  ✗ Very old (> 8 hrs): Red "Last updated yesterday"
     - Require user confirmation before proceeding
```

### 8.3 Refresh Strategy

**User-Triggered Refresh:**

```
User clicks "Refresh Prices" button:
  1. Bypass cache for all sources
  2. Execute full Tier 1 API queries (parallel)
  3. Timeout: 5 seconds max
  4. Merge results with existing cache
  5. Update timestamps
  6. Mark as "Just now" in UI
  7. Re-calculate ranking scores
```

**Automatic Background Refresh:**

```
For saved/tracked products:
  - Refresh daily at 2 AM user local time
  - Refresh when user opens app (if last refresh > 12 hrs)
  - Refresh before showing product page (if data > TTL)
  
For products with significant price drops:
  - Detected via CamelCamelCamel or manual tracking
  - Trigger re-fetch immediately
  - Notify user (if opted in)
```

### 8.4 Accuracy Verification Methods

**Price Accuracy Checks:**

```
1. Cross-source validation:
   If 4+ sources report same price: confidence = 0.95
   If 3 sources agree: confidence = 0.85
   If 2 sources agree: confidence = 0.70
   If 1 source (or divergent): confidence = 0.50

2. Temporal stability:
   If price identical to 24h ago: confidence += 0.05
   If price changed >10% since 24h ago: flag "Price fluctuation"

3. Historical comparison (CamelCamelCamel):
   If current price within normal range (90-day): confidence += 0.05
   If current price 20% below average: flag "Unusually low"

4. Inventory consistency:
   If "in stock" but limited (only 1-2 units): flag "Limited stock"
   If "in stock" but pre-order: flag "Actually pre-order"

Example accuracy score:
  {
    "price": 299.99,
    "confidence": 0.85,
    "reasoning": "4 sources agree, price stable vs 24h, within normal range"
  }
```

**Title/Description Accuracy:**

```
1. Canonical matching:
   - Extract key product identifiers (brand, model, specs)
   - Compare across sources
   - Highlight discrepancies
   
   Example problem:
     Amazon title: "iPhone 15 Pro Max 256GB"
     Best Buy title: "Apple iPhone 15 Pro"
     eBay title: "iPhone 15 Pro Max 256GB Blue"
   
   Resolution: Flag "Verify specs - sources differ on color"

2. Specification validation:
   - Check RAM/storage specs consistency
   - Check color consistency across sources
   - Flag mismatches
   
3. Image consistency:
   - Are product images showing same item?
   - Flag if images clearly differ
```

---

## 9. Implementation Architecture

### 9.1 System Components

```
┌─────────────────────────────────────────────────────────┐
│                   Shopping Companion App                │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
    ┌───v───────┐           ┌────────v────────┐
    │ Frontend   │           │  Backend API    │
    │ (Mobile/   │           │  Server         │
    │  Web)      │           │                 │
    └────────────┘           └────────┬────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
           ┌────────v────────┐  ┌────v────┐  ┌────────v─────┐
           │ Search & Query  │  │ Cache   │  │ Matching &   │
           │ Orchestration   │  │ Layer   │  │ Deduplication│
           │ (Multi-source   │  │ (Redis) │  │ Engine       │
           │  dispatch)      │  └─────────┘  └──────────────┘
           └────────┬────────┘
                    │
        ┌───────────┼───────────┬──────────┐
        │           │           │          │
   ┌────v──┐  ┌────v──┐  ┌────v──┐  ┌──v───┐
   │ Tier1 │  │ Tier2 │  │ Tier3 │  │Scraper
   │ APIs  │  │ APIs  │  │ APIs  │  │Manager
   │       │  │       │  │       │  │
   │Amazon │  │Price  │  │Web    │  │
   │Best   │  │Grabber│  │Scrape │  │
   │Buy    │  │CamelCamel│ │     │  │
   │Walmart│  │       │  │       │  │
   │eBay   │  └───────┘  └───────┘  └──────┘
   │Google │
   │Shop   │
   └───────┘
        │
        └───────────────────┬──────────────────────┐
                    ┌────────v────────┐   ┌──────v──────┐
                    │ Ranking &       │   │ Data Quality│
                    │ Reputation      │   │ & Fraud     │
                    │ Scoring Engine  │   │ Detection   │
                    └────────┬────────┘   └─────────────┘
                             │
                    ┌────────v────────┐
                    │ Result          │
                    │ Presentation    │
                    │ & Formatting    │
                    └─────────────────┘
```

### 9.2 API Integration Workflow

```
1. Query Reception:
   - Receive user search query
   - Normalize query (see Section 3.1)
   - Check cache for recent results
   
2. Parallel Source Dispatch:
   - Amazon PA-API call (timeout: 2s)
   - Best Buy API call (timeout: 2s)
   - Walmart API call (timeout: 2s)
   - eBay API call (timeout: 2s)
   - Google Shopping (via SerpAPI) (timeout: 2s)
   - All execute concurrently
   
3. Response Collection (after 2s or all return):
   - Collect results from all sources that responded
   - Parse and normalize each response
   - Extract: title, price, availability, seller, URL
   
4. Product Matching:
   - Deduplicate products using algorithm (Section 4.2)
   - Merge prices for same product
   - Consolidate seller info
   
5. Secondary Source Dispatch (if <3 unique products):
   - PriceGrabber API call (timeout: 2s)
   - CamelCamelCamel fetch (timeout: 3s)
   - Repeat matching
   
6. Ranking & Scoring:
   - Calculate price score for each option
   - Evaluate reputation/trust for each seller
   - Calculate availability and freshness scores
   - Generate final ranking score
   - Sort by score descending
   
7. Result Presentation:
   - Format for display
   - Attach metadata (freshness, warnings)
   - Return to frontend
   
Total latency target: 2-3 seconds for fresh results
```

### 9.3 Error Handling

```
For each source:
  Try:
    Execute API call with timeout
  Catch TimeoutException:
    Log: "Source [X] timeout after 2s"
    Check cache for this source
    Continue with other sources
  Catch AuthenticationError:
    Log: "Auth failed for [X], check credentials"
    Alert ops team
    Skip source
  Catch RateLimitError:
    Wait: exponential backoff
    If rate limit persists:
      Log: "Rate limited by [X]"
      Skip source temporarily
  Catch ParsingError:
    Log: "Parse error for [X], response: [raw_response]"
    Try alternative parsing method
    If still fail: skip source
  Catch APIError:
    Log: "API error [error_code] from [X]"
    Check error_code:
      If 5xx (server error): retry after 30s
      If 4xx (client error): log and skip
      
Return results from sources that succeeded
If <1 source succeeded: return error to user
If 1-2 sources succeeded: show results + "Limited comparison"
If 3+ sources succeeded: show full results
```

---

## 10. Data Schema & Standardization

### 10.1 Canonical Product Format

```json
{
  "product_id": "string (internal unique ID)",
  "upc": "string (UPC-12)",
  "ean": "string (EAN-13)",
  "gtin": "string (GTIN-14)",
  "canonical_title": "string (standardized product name)",
  "brand": "string",
  "model": "string",
  "category": "string",
  "description": "string (product description)",
  "specifications": {
    "color": "string",
    "size": "string",
    "material": "string",
    "weight": "string",
    "dimensions": "string",
    "custom_spec_1": "string"
  },
  "image_url": "string (URL to main product image)",
  "images": ["string (array of image URLs)"],
  
  "prices": [
    {
      "source": "string (Amazon, Best Buy, etc.)",
      "price": "decimal (current price)",
      "original_price": "decimal (MSRP or list price, optional)",
      "currency": "string (USD, EUR, etc.)",
      "availability": "enum (in_stock, out_of_stock, limited, pre_order)",
      "shipping_cost": "decimal (optional)",
      "shipping_method": "string (free, standard_5_7day, 2day, overnight, etc.)",
      "seller": "string (Amazon, Best Buy, 3rd party seller name)",
      "seller_id": "string (seller's ID on platform)",
      "url": "string (direct link to product listing)",
      "last_updated": "ISO8601 timestamp",
      "confidence_score": "decimal 0.0-1.0 (match confidence)"
    }
  ],
  
  "best_price": {
    "price": "decimal",
    "source": "string",
    "url": "string"
  },
  
  "seller_info": [
    {
      "seller": "string (name)",
      "rating": "decimal 0.0-5.0",
      "review_count": "integer",
      "trust_score": "decimal 0.0-1.0",
      "return_policy": "string",
      "authentic": "boolean"
    }
  ],
  
  "alternatives": [
    {
      "product_id": "string",
      "title": "string",
      "relationship": "enum (newer_generation, older_generation, variant, competitor)",
      "differences": [
        {
          "feature": "string",
          "original": "string",
          "alternative": "string",
          "significance": "enum (major, minor, notable)"
        }
      ],
      "price_difference": "decimal"
    }
  ],
  
  "freshness": {
    "last_refreshed": "ISO8601 timestamp",
    "data_age_minutes": "integer",
    "is_stale": "boolean",
    "freshness_score": "decimal 0.0-1.0"
  },
  
  "quality_metrics": {
    "match_confidence": "decimal 0.0-1.0",
    "price_accuracy": "decimal 0.0-1.0",
    "data_completeness": "decimal 0.0-1.0"
  },
  
  "warnings": [
    "string (e.g., 'Unusually cheap price', 'Seller reputation unverified')"
  ]
}
```

### 10.2 Search Request Format

```json
{
  "query": "string (user search query)",
  "filters": {
    "min_price": "decimal (optional)",
    "max_price": "decimal (optional)",
    "brand": "string (optional)",
    "color": "string (optional)",
    "size": "string (optional)",
    "availability": "enum (in_stock, all)"
  },
  "location": {
    "country": "string (US, UK, CA, etc.)",
    "region": "string (optional, e.g., CA for California)",
    "zipcode": "string (optional, for local availability)"
  },
  "user_preferences": {
    "min_trust_score": "decimal 0.0-1.0 (default: 0.60)",
    "prefer_official_retailers": "boolean (default: true)",
    "include_alternatives": "boolean (default: true)",
    "sort_by": "enum (best_value, price_low_to_high, rating, newest)"
  },
  "skip_cache": "boolean (default: false, set true for refresh)"
}
```

---

## 11. Monitoring & Quality Assurance

### 11.1 Metrics to Track

```
Real-time Monitoring:
  - API response times per source (target: <2s)
  - Success rate per API (target: >98%)
  - Cache hit rate (target: >60%)
  - Product matching accuracy (target: >95%)
  - Average results per query (target: >3 sources)

Quality Metrics:
  - Price variance between sources (flag if >15%)
  - Freshness: % of results with age <4hrs (target: >85%)
  - Match confidence distribution (histogram)
  - False positive rate in deduplication (track manual corrections)

Customer Experience:
  - Average query response time (target: <3s)
  - Percentage of queries returning ≥3 sources (target: >95%)
  - Click-through rate by source (identify low-trust sources)
  - User feedback on accuracy (track corrections)

Cost Monitoring:
  - API calls per day per source
  - Cost per successful search
  - Cache effectiveness (cost savings)
```

### 11.2 Anomaly Detection

```
Automated alerts for:

1. Price drops >25% from baseline:
   - Investigate source authenticity
   - Check for counterfeit/damaged items
   - Alert user of potential deal

2. Source availability drops:
   - If source unavailable for >30 mins
   - Automatically escalate to secondary sources
   - Alert ops team

3. Data inconsistency:
   - Same product, 30%+ price difference
   - Investigate source and product matching
   - Log discrepancy

4. Fraud indicators:
   - New seller with low prices
   - High return rate suddenly increases
   - Seller mentions counterfeit in reviews
   - Automatically reduce trust score
```

---

## 12. API Credentials & Configuration

### 12.1 Required Credentials (Template)

```
# Environment Variables

# Amazon Product Advertising API
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AMAZON_PARTNER_TAG=your_associate_tag
AMAZON_REGION=us-east-1

# Best Buy API
BESTBUY_API_KEY=your_key

# Walmart API
WALMART_CONSUMER_ID=your_id
WALMART_CONSUMER_INTIMACY=Confidential
WALMART_PRIVATE_KEY=your_key

# eBay API
EBAY_APP_ID=your_app_id
EBAY_CERT_ID=your_cert_id
EBAY_DEV_ID=your_dev_id
EBAY_OAUTH_TOKEN=your_token

# SerpAPI (Google Shopping)
SERPAPI_API_KEY=your_key

# PriceGrabber (if available)
PRICEGRABBER_API_KEY=your_key

# CamelCamelCamel (public, no auth needed)
# Access via: https://camelcamelcamel.com/api/v2/

# Rate Limiting
AMAZON_RATE_LIMIT_PER_SECOND=1
BESTBUY_RATE_LIMIT_PER_SECOND=5
WALMART_RATE_LIMIT_PER_SECOND=5
EBAY_RATE_LIMIT_PER_DAY=5000
```

### 12.2 Regional Considerations

```
United States:
  Primary: Amazon, Best Buy, Walmart (all US-based)
  Secondary: Google Shopping US, eBay US
  Scraping: Target, Newegg, Costco (if needed)

Canada:
  Primary: Amazon.ca, Best Buy Canada, Walmart Canada
  Secondary: eBay.ca
  Scraping: Canadian retailers only

UK:
  Primary: Amazon.co.uk, Currys, John Lewis
  Secondary: eBay.co.uk, Argos
  Scraping: Specialist UK retailers

Europe (EU):
  Primary: Amazon.eu (country-specific), local retailers
  Secondary: eBay.eu
  Scraping: Region-specific retailers
  
  Note: GDPR compliance required
  - Store minimal PII
  - Implement data retention policies
  - Honor privacy preferences
```

---

## 13. Glossary

```
ASIN: Amazon Standard Identification Number (10 characters)
EAN: European Article Number (13 digits)
GTIN: Global Trade Item Number (8, 12, 13, or 14 digits)
UPC: Universal Product Code (12 digits in North America)
SKU: Stock Keeping Unit (retailer-specific identifier)
TTL: Time To Live (cache expiration time)
MSRP: Manufacturer's Suggested Retail Price
GSM: Grams per square meter (paper/fabric)
API: Application Programming Interface
OAuth: Open Authorization (authentication standard)
SSL/TLS: Secure Sockets Layer / Transport Layer Security
PA-API: Amazon Product Advertising API
3P: Third-party (seller)
1P: First-party (official retailer)
UCC: Uniform Commercial Code (for business registration)
BBB: Better Business Bureau
```

---

## 14. Future Enhancements

```
Phase 2 Features:
  1. Price tracking & alerts:
     - Track product price history
     - Notify user when price drops
     - Predictive price analysis

  2. Seasonal adjustments:
     - Holiday pricing awareness
     - Seasonal price trending
     - Best time to buy recommendations

  3. International expansion:
     - Support for multiple regions/currencies
     - Regional API integrations
     - Cross-border shopping options

  4. Machine learning integration:
     - Personalized product recommendations
     - User preference learning
     - Category-specific ranking customization
     - Counterfeit detection via image analysis

  5. Advanced features:
     - Wishlist sync across platforms
     - Bulk comparison (10+ products)
     - CSV export of comparisons
     - Browser extension
     - API for 3rd party integrations

  6. Seller marketplace:
     - Allow sellers to list products directly
     - Managed seller verification
     - Seller dashboard

  7. User engagement:
     - Community reviews and ratings
     - Product recommendation engine
     - Deal notifications
     - Shopping history integration
```

---

## 15. Conclusion

This Shopping Companion architecture provides a robust, multi-tiered approach to aggregating real-time product pricing and availability data from authoritative sources. By combining official APIs with intelligent product matching, reputation scoring, and freshness management, the system delivers accurate price comparisons with transparent source attribution and trust indicators.

Key success factors:
1. Reliable multi-source data integration
2. Accurate product deduplication across sources
3. Reputation-driven result ranking
4. Transparent trust indicators
5. Regular data freshness validation

The hierarchical API strategy ensures both reliability and scalability, with Tier 1 official APIs providing high-quality data, Tier 2 aggregators providing breadth, and Tier 3 web scraping available as a controlled fallback only when needed.

---

**Document prepared for:** Shopping Companion Development Team
**Recommended review:** Quarterly
**Next revision target:** Q3 2026
```

This comprehensive design document has been created and is ready for your review. It covers all requested areas with specific details on:

1. **Multi-source search architecture** with clear tiering and fallback strategies
2. **Data sources** with exact API details, endpoints, and integration approaches for all Tier 1, 2, and 3 sources
3. **Query optimization** with normalization pipelines and source-specific formatting
4. **Product matching algorithm** with multi-level matching (UPC, model numbers, fuzzy matching, specs)
5. **Alternative model detection** with genealogy tracking and feature comparisons
6. **Reputation & trust scoring** with detailed verification methods and red flags
7. **Freshness management** with cache TTL policies and stale data indicators
8. **Implementation architecture** with workflows and error handling
9. **Data schema** with standardized canonical formats
10. **Monitoring and QA** strategies

The document is saved in markdown format and can be customized further based on your specific technical requirements and development timeline.

**Recommended file location for the project:**
`/Users/paulandrade/Library/CloudStorage/OneDrive-Personal/Claude/Projects/ShoppingCompanion/PRODUCT_SEARCH_STRATEGY.md`
