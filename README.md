# Luno-automation-asset-tracker-Crypto-Trading-
A lightweight Python CLI &amp; SQLite application that integrates with the Luno API for zero-friction access, order-level crypto position tracking, and automated fee-adjusted net P&amp;L calculations.

**Designed** to overcome the limitations of single-average price aggregation found in standard exchange apps, this project introduces **Order-Level Tracking** — treating each buy order as an independent position to calculate accurate unrealized P&L against live market prices. Leveraging secure API keys, users can instantly check balances, pending order statuses, and profit statements from the command-line interface without navigating repeated web logins or 2FA prompts. Furthermore, the system features an **On-Demand Synchronization engine** powered by optimized SQL `UNION ALL` queries, ensuring single-pass order status updates without background CPU or RAM drain.

### 📱 Official Luno App vs. 🚀 Luno Crypto Tracker 

While the official Luno app/web portal is great for executing basic trades, this project solves key pain points for active traders and tracking enthusiasts: --- 

### 1\. 🔑 Authentication &amp; Access 
📱 Official Luno App / Web: Requires repeated web logins, passwords, and multi-factor authentication (2FA/biometric) steps every time you want to check your portfolio performance. 

🚀 This Project (Luno Crypto Tracker): 
Zero Friction. Secure API keys allow instant, scriptable status checks via the command-line interface (CLI) without manual logins or 2FA prompts. --- 

### 2\. 🎯 Granular Asset Tracking
📱 Official Luno App / Web: Aggregates all coin purchases together into a single average buy price, making lot-level tracking difficult. 

🚀 This Project (Luno Crypto Tracker):
Order-Level Lot Tracking. Treats every individual buy order as an independent position to track precise floating P&L against live market prices. --- 

### 3\. 💵 Closed Trade Accounting &amp; P&L 
📱 Official Luno App / Web: Historical records can be cluttered and require manual tracking on spreadsheets for accurate net P&L.

🚀 This Project (Luno Crypto Tracker): Automated Profit Statement. Realized trades are logged into a permanent profit/loss history automatically, calculating true net profit after deducting all Luno transaction fees (\`fee\_counter\`). --- 

### 📊 Comparison Summary Table 

1\. Authentication &amp; Access 
- Official Luno App / Web: Requires repeated web logins &amp; 2FA prompts
- This Project: Zero Friction. Instant API status checks via CLI

2\. Asset Tracking
- Official Luno App / Web: Single aggregated average buy price
- This Project: Order-Level Lot Tracking. Each buy is independent

3\. Profit &amp; Loss (P&amp;L) 
- Official Luno App / Web: Manual spreadsheet tracking needed
- This Project: Automated. Net profit logged after exchange fees

4\. System Footprint 
- Official Luno App / Web: Full GUI / Web App overhead 
- This Project: Lightweight. On-Demand Sync saves CPU/RAM
