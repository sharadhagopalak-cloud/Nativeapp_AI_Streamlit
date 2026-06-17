import io
import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from typing import Tuple, Dict, Any

st.set_page_config(page_title="Retail Sales Intelligence App", layout="wide")

# Helper: map common column name variants to canonical names
COMMON_WEEKLY_VARIANTS = {
    'Week': ['week', 'wk', 'weekstartdate', 'week_start_date', 'week start date', 'weekstart', 'week_start'],
    'Store_ID': ['storeid', 'store id', 'store_id'],
    'Product_Category': ['productcategory', 'product category', 'category'],
    'Gross_Sales': ['grosssales', 'gross sales', 'gross_sale', 'gross_sale_amount'],
    'Return_Amount': ['returnamount', 'return amount', 'returns'],
    'Target_Sales': ['targetsales', 'target sales', 'target_sales'],
    'Total_Transactions': ['totaltransactions', 'total transactions', 'transactions'],
    'Total_Discount': ['totaldiscount', 'total discount', 'discounts'],
    'Stockout_Event': ['stockoutevent', 'stockout event', 'stockout']
}

COMMON_MASTER_VARIANTS = {
    'Store_ID': ['storeid', 'store id', 'store_id'],
    'Store_Name': ['storename', 'store name', 'store'],
    'Region': ['region', 'area'],
    'City': ['city', 'town'],
    'Store_Format': ['storeformat', 'store format', 'format']
}


def _apply_variants(df: pd.DataFrame, variants: Dict[str, list]):
    rename_map = {}
    for col in list(df.columns):
        cleaned = col.strip().lower().replace(' ', '').replace('_', '')
        for canon, vals in variants.items():
            if cleaned == canon.lower().replace('_', '') or cleaned in vals:
                rename_map[col] = canon
                break
    if rename_map:
        df.rename(columns=rename_map, inplace=True)


@st.cache_data
def load_and_merge_data(weekly_file, master_file) -> Tuple[pd.DataFrame | None, str | None, Dict[str, Any] | None]:
    """Load two Excel-like uploads, normalize columns, merge on `Store_ID` and return merged dataframe plus diagnostics."""
    try:
        # Accept both file paths and uploaded file-like objects
        df_weekly = pd.read_excel(weekly_file)
        df_master = pd.read_excel(master_file)

        # Strip column names
        df_weekly.columns = df_weekly.columns.str.strip()
        df_master.columns = df_master.columns.str.strip()

        # Apply tolerant mapping
        _apply_variants(df_weekly, COMMON_WEEKLY_VARIANTS)
        _apply_variants(df_master, COMMON_MASTER_VARIANTS)

        # Validate Store_ID existence
        if 'Store_ID' not in df_weekly.columns or 'Store_ID' not in df_master.columns:
            msg_parts = []
            if 'Store_ID' not in df_weekly.columns:
                msg_parts.append(f"Weekly file missing 'Store_ID'. Found: {list(df_weekly.columns)}")
            if 'Store_ID' not in df_master.columns:
                msg_parts.append(f"Master file missing 'Store_ID'. Found: {list(df_master.columns)}")
            return None, '; '.join(msg_parts), None

        # Ensure numeric fields exist and convert safely
        numeric_cols = ['Gross_Sales', 'Return_Amount', 'Target_Sales', 'Total_Transactions', 'Total_Discount', 'Stockout_Event']
        for col in numeric_cols:
            if col in df_weekly.columns:
                df_weekly[col] = pd.to_numeric(df_weekly[col], errors='coerce').fillna(0)
            else:
                df_weekly[col] = 0

        # Normalize Store_ID as strings (many datasets use 'ST-001' style IDs)
        df_weekly['Store_ID'] = df_weekly['Store_ID'].astype(str).str.strip().str.upper()
        df_master['Store_ID'] = df_master['Store_ID'].astype(str).str.strip().str.upper()

        # Drop rows with empty or missing Store_ID
        df_weekly = df_weekly[df_weekly['Store_ID'].notna() & (df_weekly['Store_ID'].str.len() > 0)]
        df_master = df_master[df_master['Store_ID'].notna() & (df_master['Store_ID'].str.len() > 0)]

        # Merge
        merged = pd.merge(df_weekly, df_master, on='Store_ID', how='inner')

        # Ensure downstream columns exist
        for col in numeric_cols:
            if col not in merged.columns:
                merged[col] = 0

        # Categorical defaults
        for cat_col in ['Week', 'Region', 'City', 'Store_Name', 'Store_Format', 'Product_Category']:
            if cat_col not in merged.columns:
                merged[cat_col] = 'Unknown'

        merged['Net_Sales'] = merged['Gross_Sales'] - merged['Return_Amount']

        summary = {
            'weekly_rows': int(df_weekly.shape[0]),
            'master_rows': int(df_master.shape[0]),
            'merged_rows': int(merged.shape[0]),
            'weekly_columns': list(df_weekly.columns),
            'master_columns': list(df_master.columns)
        }

        return merged, None, summary
    except Exception as e:
        return None, str(e), None


def generate_sample_data() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    import random
    random.seed(42)

    stores = [
        {"Store_ID": 1001, "Store_Name": "Oakridge Plaza", "Region": "West", "City": "San Francisco", "Store_Format": "Supermarket"},
        {"Store_ID": 1002, "Store_Name": "Piedmont Avenue", "Region": "South", "City": "Atlanta", "Store_Format": "Express"},
        {"Store_ID": 1003, "Store_Name": "Metro Hub Centre", "Region": "North", "City": "Chicago", "Store_Format": "Hypermarket"},
    ]
    df_master = pd.DataFrame(stores)

    categories = ["Electronics", "Apparel", "Groceries"]
    weeks = [f"Week {i:02d}" for i in range(1, 5)]

    weekly_records = []
    for week in weeks:
        for store in stores:
            for cat in categories:
                gross = random.uniform(5000, 30000)
                ret = gross * random.uniform(0.01, 0.06)
                target = gross * random.uniform(0.9, 1.2)
                transactions = random.randint(100, 800)
                discount = gross * random.uniform(0.01, 0.1)
                stockout = 1 if random.random() < 0.1 else 0
                weekly_records.append({
                    'Week': week,
                    'Store_ID': store['Store_ID'],
                    'Product_Category': cat,
                    'Gross_Sales': round(gross, 2),
                    'Return_Amount': round(ret, 2),
                    'Target_Sales': round(target, 2),
                    'Total_Transactions': transactions,
                    'Total_Discount': round(discount, 2),
                    'Stockout_Event': stockout
                })

    df_weekly = pd.DataFrame(weekly_records)
    merged = pd.merge(df_weekly, df_master, on='Store_ID', how='inner')
    merged['Net_Sales'] = merged['Gross_Sales'] - merged['Return_Amount']

    summary = {
        'weekly_rows': int(df_weekly.shape[0]),
        'master_rows': int(df_master.shape[0]),
        'merged_rows': int(merged.shape[0]),
        'weekly_columns': list(df_weekly.columns),
        'master_columns': list(df_master.columns)
    }
    return merged, summary


# ------------------
# UI
# ------------------
st.title("Retail Sales Intelligence App")
st.sidebar.title("Data Ingestion & Controls")
st.sidebar.markdown("Upload your Weekly Sales and Store Master Excel files below.")

weekly_uploader = st.sidebar.file_uploader("Weekly Sales (.xlsx)", type=["xlsx"])
master_uploader = st.sidebar.file_uploader("Store Master (.xlsx)", type=["xlsx"])
use_sample = st.sidebar.checkbox("Use Sample Data", value=False)

# Option: load directly from default local data files
LOAD_FROM_DISK = st.sidebar.checkbox("Use default local Excel files", value=False)
DEFAULT_WEEKLY_PATH = r"C:\Users\sharadha.gopalak\Downloads\StackAI Foundation - AI Native App Building Assignment - Level 1\StackAI Foundation - AI Native App Building Assignment - Level 1\data\retail_weekly_sales.xlsx"
DEFAULT_MASTER_PATH = r"C:\Users\sharadha.gopalak\Downloads\StackAI Foundation - AI Native App Building Assignment - Level 1\StackAI Foundation - AI Native App Building Assignment - Level 1\data\store_master.xlsx"
if LOAD_FROM_DISK:
    try:
        # if files exist, set uploaders to file paths so load_and_merge_data can read them
        import os
        if os.path.exists(DEFAULT_WEEKLY_PATH) and os.path.exists(DEFAULT_MASTER_PATH):
            weekly_uploader = DEFAULT_WEEKLY_PATH
            master_uploader = DEFAULT_MASTER_PATH
            st.sidebar.success("Loading files from default disk paths.")
        else:
            st.sidebar.error("Default files not found at expected paths. Please upload manually.")
    except Exception:
        st.sidebar.error("Error accessing default files. Please upload manually.")

df = None
summary = None
error_msg = None

if weekly_uploader is not None and master_uploader is not None:
    df, error_msg, summary = load_and_merge_data(weekly_uploader, master_uploader)
    if error_msg:
        st.sidebar.error(f"Error merging files: {error_msg}")
    else:
        st.sidebar.success("Files merged successfully.")
elif use_sample:
    df, summary = generate_sample_data()
    st.sidebar.info("Using sample data for preview.")
else:
    st.sidebar.info("Upload both files to enable the dashboard (or enable Sample Data).")

# Show diagnostics if available
if summary is not None:
    st.sidebar.markdown("**Upload Summary**")
    st.sidebar.write({
        'Weekly rows': summary.get('weekly_rows'),
        'Master rows': summary.get('master_rows'),
        'Merged rows': summary.get('merged_rows')
    })
    st.sidebar.caption(f"Weekly cols: {summary.get('weekly_columns')}")
    st.sidebar.caption(f"Master cols: {summary.get('master_columns')}")
    # Also log summary to server stdout so we can tail logs remotely
    try:
        print("UPLOAD_SUMMARY:", summary)
    except Exception:
        pass

if df is None:
    st.info("Please upload both files in the sidebar to see the dashboard, or enable Sample Data.")
    st.stop()

# Build cascading (dependent) filters
st.sidebar.subheader("Filters")

def _opts(df_subset, col):
    """Return sorted, display-friendly options for a column from a dataframe subset, handling mixed datetimes and strings."""
    if col not in df_subset.columns or df_subset.empty:
        return []
    vals = df_subset[col].dropna().unique()
    items = []
    for v in vals:
        # handle pandas Timestamp / datetime
        if isinstance(v, (pd.Timestamp, datetime.datetime)):
            dt = pd.Timestamp(v)
            items.append((0, dt.to_datetime64(), dt.strftime('%Y-%m-%d')))
            continue
        # try parseable strings
        try:
            parsed = pd.to_datetime(v)
            if not pd.isna(parsed):
                dt = pd.Timestamp(parsed)
                items.append((0, dt.to_datetime64(), dt.strftime('%Y-%m-%d')))
                continue
        except Exception:
            pass
        # fallback: string sort key
        items.append((1, str(v).lower(), str(v)))

    # sort: datetimes first by date, then strings alphabetically
    items_sorted = sorted(items, key=lambda t: (t[0], t[1]))
    return [display for _flag, _key, display in items_sorted]

# Cascade: each filter option depends on prior selections
df_for_opts = df.copy()

# Week filter
week_opts = _opts(df_for_opts, 'Week')
selected_weeks = st.sidebar.multiselect('Week', options=week_opts)
if selected_weeks:
    df_for_opts = df_for_opts[df_for_opts['Week'].isin(selected_weeks)]

# Region filter (only shows regions available in selected weeks)
region_opts = _opts(df_for_opts, 'Region')
selected_regions = st.sidebar.multiselect('Region', options=region_opts)
if selected_regions:
    df_for_opts = df_for_opts[df_for_opts['Region'].isin(selected_regions)]

# City filter (only shows cities in selected region)
city_opts = _opts(df_for_opts, 'City')
selected_cities = st.sidebar.multiselect('City', options=city_opts)
if selected_cities:
    df_for_opts = df_for_opts[df_for_opts['City'].isin(selected_cities)]

# Store Name filter (only shows stores in selected city)
store_opts = _opts(df_for_opts, 'Store_Name')
selected_stores = st.sidebar.multiselect('Store Name', options=store_opts)
if selected_stores:
    df_for_opts = df_for_opts[df_for_opts['Store_Name'].isin(selected_stores)]

# Store Format filter (only shows formats available in selected stores)
format_opts = _opts(df_for_opts, 'Store_Format')
selected_formats = st.sidebar.multiselect('Store Format', options=format_opts)
if selected_formats:
    df_for_opts = df_for_opts[df_for_opts['Store_Format'].isin(selected_formats)]

# Product Category filter (only shows categories in selected stores/formats)
cat_opts = _opts(df_for_opts, 'Product_Category')
selected_cats = st.sidebar.multiselect('Product Category', options=cat_opts)

# Apply all filters to get final dataset
df_filtered = df.copy()
if selected_weeks:
    df_filtered = df_filtered[df_filtered['Week'].isin(selected_weeks)]
if selected_regions:
    df_filtered = df_filtered[df_filtered['Region'].isin(selected_regions)]
if selected_cities:
    df_filtered = df_filtered[df_filtered['City'].isin(selected_cities)]
if selected_stores:
    df_filtered = df_filtered[df_filtered['Store_Name'].isin(selected_stores)]
if selected_formats:
    df_filtered = df_filtered[df_filtered['Store_Format'].isin(selected_formats)]
if selected_cats:
    df_filtered = df_filtered[df_filtered['Product_Category'].isin(selected_cats)]

if df_filtered.empty:
    st.warning("No records match the active combination of dynamic filters. Please adjust your criteria.")
    with st.expander("Diagnostics", expanded=True):
        st.markdown("**Active filters**")
        st.write({
            'Week': selected_weeks,
            'Region': selected_regions,
            'City': selected_cities,
            'Store Name': selected_stores,
            'Store Format': selected_formats,
            'Product Category': selected_cats
        })
        st.markdown("**Merged row preview (top 20)**")
        st.dataframe(df.head(20))
    st.stop()

# KPI calculations
sum_gross = df_filtered['Gross_Sales'].sum()
sum_return = df_filtered['Return_Amount'].sum()
sum_net = df_filtered['Net_Sales'].sum()
sum_target = df_filtered['Target_Sales'].sum()
sum_txn = df_filtered['Total_Transactions'].sum()
sum_discount = df_filtered['Total_Discount'].sum()
sum_stockouts = int(df_filtered['Stockout_Event'].sum())

target_ach = (sum_net / sum_target * 100) if sum_target > 0 else 0.0
atv = (sum_net / sum_txn) if sum_txn > 0 else 0.0
return_rate = (sum_return / sum_net * 100) if sum_net > 0 else 0.0
discount_rate = (sum_discount / sum_gross * 100) if sum_gross > 0 else 0.0

st.markdown("### Executive Key Performance Indicators")
k1, k2, k3, k4, k5 = st.columns(5)

k1.metric("Net Sales", f"${sum_net:,.2f}")
k2.metric("Target Achievement %", f"{target_ach:.2f}%")
k3.metric("Avg Transaction Value (ATV)", f"${atv:,.2f}")
k4.metric("Return Rate %", f"{return_rate:.2f}%")
k5.metric("Discount Rate %", f"{discount_rate:.2f}%")

st.markdown("---")

# Charts
tab1, tab2, tab3 = st.tabs(["Visuals", "Insights", "Data & Export"]) 

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        if 'Week' in df_filtered.columns:
            weekly_trend = df_filtered.groupby('Week')['Net_Sales'].sum().reset_index()
        else:
            weekly_trend = pd.DataFrame({'Week': ['Unknown'], 'Net_Sales': [df_filtered['Net_Sales'].sum()]})
        fig = px.line(weekly_trend, x='Week', y='Net_Sales', title='Weekly Net Sales Trend', markers=True, template='plotly_white')
        fig.update_layout(hovermode='x unified')
        st.plotly_chart(fig, width='stretch')
    with col2:
        regional = df_filtered.groupby('Region')['Net_Sales'].sum().reset_index().sort_values('Net_Sales', ascending=False)
        fig2 = px.bar(regional, x='Region', y='Net_Sales', title='Net Sales by Region', color='Region', template='plotly_white')
        st.plotly_chart(fig2, width='stretch')

    col3, col4 = st.columns(2)
    with col3:
        # leaderboard
        top_n = min(20, df_filtered['Store_Name'].nunique() if 'Store_Name' in df_filtered.columns else 1)
        top_n = st.slider('Top N stores', 3, max(3, top_n), value=min(10, top_n))
        store_data = df_filtered.groupby('Store_Name')['Net_Sales'].sum().reset_index().sort_values('Net_Sales', ascending=True).tail(top_n)
        fig3 = px.bar(store_data, x='Net_Sales', y='Store_Name', orientation='h', title=f'Top {top_n} Stores (Net Sales)', color='Net_Sales', template='plotly_white')
        st.plotly_chart(fig3, width='stretch')
    with col4:
        cat_data = df_filtered.groupby('Product_Category')['Net_Sales'].sum().reset_index()
        fig4 = px.pie(cat_data, values='Net_Sales', names='Product_Category', title='Net Sales by Category', hole=0.35, template='plotly_white')
        st.plotly_chart(fig4, width='stretch')

with tab2:
    st.markdown("### Operational Summary & Insights")
    st.metric("Total Stockout Risks Detected", sum_stockouts)

    # region leaders
    if not regional.empty:
        best = regional.iloc[0]
        worst = regional.iloc[-1]
        st.markdown(f"- **Top Region:** {best['Region']} (${best['Net_Sales']:,.2f})")
        st.markdown(f"- **Lowest Region:** {worst['Region']} (${worst['Net_Sales']:,.2f})")

    st.markdown("---")

    # High Return Categories
    st.markdown("### High Return Categories")
    cat_returns = df_filtered.groupby('Product_Category').agg({
        'Return_Amount': 'sum',
        'Net_Sales': 'sum'
    }).reset_index()
    cat_returns['Return_Rate_%'] = (cat_returns['Return_Amount'] / (cat_returns['Return_Amount'] + cat_returns['Net_Sales']) * 100).round(2)
    cat_returns = cat_returns.sort_values('Return_Rate_%', ascending=False)
    
    col_ret1, col_ret2 = st.columns(2)
    with col_ret1:
        if not cat_returns.empty:
            fig_ret = px.bar(cat_returns, x='Product_Category', y='Return_Rate_%', 
                            title='Return Rate by Product Category', color='Return_Rate_%', 
                            color_continuous_scale='Reds', template='plotly_white')
            st.plotly_chart(fig_ret, use_container_width=True)
    with col_ret2:
        st.dataframe(cat_returns[['Product_Category', 'Return_Amount', 'Return_Rate_%']].assign(
            Return_Amount=lambda d: d['Return_Amount'].map('${:,.2f}'.format)
        ), use_container_width=True)

    st.markdown("---")

    # stores missing targets
    st.markdown("### Stores Missing Target")
    store_targets = df_filtered.groupby(['Store_Name', 'Region'])[['Net_Sales', 'Target_Sales']].sum().reset_index()
    store_targets['Target_Gap'] = store_targets['Target_Sales'] - store_targets['Net_Sales']
    under = store_targets[store_targets['Target_Gap'] > 0].sort_values('Target_Gap', ascending=False)
    if under.empty:
        st.success('All stores are meeting or exceeding targets for the filtered selection.')
    else:
        st.warning(f"{len(under)} stores below target in the current slice.")
        st.dataframe(under.assign(Target_Sales=lambda d: d['Target_Sales'].map('${:,.2f}'.format), Net_Sales=lambda d: d['Net_Sales'].map('${:,.2f}'.format), Target_Gap=lambda d: d['Target_Gap'].map('${:,.2f}'.format)), use_container_width=True)

with tab3:
    st.markdown('### Filtered Data and Export')
    st.dataframe(df_filtered.reset_index(drop=True), use_container_width=True)

    csv = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button('Export filtered retail sales CSV', csv, file_name='filtered_retail_sales.csv', mime='text/csv')

st.markdown("---")
st.caption("Data merged on Store_ID. If filters are empty or disabled, check the Upload Summary in the sidebar to confirm merged row count and available columns.")
