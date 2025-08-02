# ComEd Pricing Dashboard

Personal dashboard for monitoring ComEd electricity pricing data.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the dashboard:
```bash
streamlit run streamlit_pricing_dashboard.py
```

## Features

- Real-time 5-minute pricing data from ComEd API
- Last 12 hours of pricing activity
- Weekly pricing analysis (5 weeks)
- Auto-refresh every 5 minutes
- Chicago timezone support

## Data Source

ComEd Hourly Pricing Program API 