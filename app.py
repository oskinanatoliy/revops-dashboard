import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="RevOps Dashboard", layout="wide")

# ---------- LOAD DATA ----------
@st.cache_data
def load_data():
    df = pd.read_csv("deals.csv")
    df["AQL date"] = pd.to_datetime(df["AQL date"], errors="coerce")
    df["Closing Date"] = pd.to_datetime(df["Closing Date"], errors="coerce")
    return df

df = load_data()

st.title("📊 RevOps Analytics Dashboard")

# ---------- SIDEBAR FILTERS ----------
st.sidebar.header("Filters")

countries = sorted(df["Client country"].dropna().unique())
selected_countries = st.sidebar.multiselect("Client country", countries, default=countries)

crms = sorted(df["Client CRM"].dropna().unique())
selected_crms = st.sidebar.multiselect("Client CRM", crms, default=crms)

min_date = df["AQL date"].min()
max_date = df["AQL date"].max()
date_range = st.sidebar.date_input("AQL date range", [min_date, max_date])

# Apply filters
filtered = df[
    df["Client country"].isin(selected_countries) &
    df["Client CRM"].isin(selected_crms)
]
if len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    filtered = filtered[(filtered["AQL date"] >= start) & (filtered["AQL date"] <= end)]

st.sidebar.markdown(f"**Deals in view:** {len(filtered)}")

# ---------- HELPER: WIN RATE ----------
def win_rate_by(data, col):
    closed = data[data["Stage"].isin(["Closed Won", "Closed Lost"])]
    if closed.empty:
        return pd.DataFrame(columns=[col, "win_rate", "closed_deals"])
    grp = closed.groupby(col)["Stage"].agg(
        win_rate=lambda s: (s == "Closed Won").mean(),
        closed_deals="count"
    ).reset_index()
    return grp.sort_values("win_rate", ascending=False)

# ---------- ROW 1: WIN RATE BY COUNTRY / CRM ----------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Win Rate by Country")
    wr_country = win_rate_by(filtered, "Client country")
    if not wr_country.empty:
        fig = px.bar(wr_country, x="Client country", y="win_rate",
                     hover_data=["closed_deals"], text_auto=".0%")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No closed deals in current filter selection.")

with col2:
    st.subheader("Win Rate by CRM")
    wr_crm = win_rate_by(filtered, "Client CRM")
    if not wr_crm.empty:
        fig = px.bar(wr_crm, x="Client CRM", y="win_rate",
                     hover_data=["closed_deals"], text_auto=".0%")
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No closed deals in current filter selection.")

# ---------- ROW 2: STAGE DISTRIBUTION / DEALS BY SOURCE ----------
col3, col4 = st.columns(2)

with col3:
    st.subheader("Deal Distribution by Stage")
    stage_counts = filtered["Stage"].value_counts().reset_index()
    stage_counts.columns = ["Stage", "count"]
    fig = px.pie(stage_counts, names="Stage", values="count", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("Deals by Source")
    source_counts = filtered["Source"].value_counts().reset_index()
    source_counts.columns = ["Source", "count"]
    fig = px.bar(source_counts, x="Source", y="count")
    st.plotly_chart(fig, use_container_width=True)

# ---------- ROW 3: WIN RATE vs PPC BUDGET ----------
st.subheader("Win Rate vs PPC Budget")

budget_order = ["0", "0-500", "500-1000", "1000-2000", "2000-5000", "5000-10000", "20000+"]
wr_budget = win_rate_by(filtered, "PPC budget USD")
wr_budget["PPC budget USD"] = wr_budget["PPC budget USD"].astype(str)
wr_budget["order"] = wr_budget["PPC budget USD"].apply(
    lambda x: budget_order.index(x) if x in budget_order else 99
)
wr_budget = wr_budget.sort_values("order")

if not wr_budget.empty:
    fig = px.bar(wr_budget, x="PPC budget USD", y="win_rate",
                 hover_data=["closed_deals"], text_auto=".0%",
                 category_orders={"PPC budget USD": budget_order})
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No closed deals in current filter selection.")

# ---------- DATA QUALITY CHECKS ----------
st.subheader("🔍 Data Issues")

issues = []

# 1. Closed deal but no Closing Date
mask1 = df["Stage"].isin(["Closed Won", "Closed Lost"]) & df["Closing Date"].isna()
if mask1.any():
    tmp = df[mask1].copy()
    tmp["Issue"] = "Closed deal without Closing Date"
    issues.append(tmp)

# 2. Closing Date earlier than AQL date
mask2 = df["Closing Date"].notna() & (df["Closing Date"] < df["AQL date"])
if mask2.any():
    tmp = df[mask2].copy()
    tmp["Issue"] = "Closing Date earlier than AQL date"
    issues.append(tmp)

# 3. Closed Lost but no Loss reason description
mask3 = (df["Stage"] == "Closed Lost") & df["Loss reason description"].isna()
if mask3.any():
    tmp = df[mask3].copy()
    tmp["Issue"] = "Closed Lost without a Loss reason"
    issues.append(tmp)

# 4. Not closed (open stage) but Closing Date is filled
mask4 = ~df["Stage"].isin(["Closed Won", "Closed Lost"]) & df["Closing Date"].notna()
if mask4.any():
    tmp = df[mask4].copy()
    tmp["Issue"] = "Closing Date filled on a deal that isn't closed"
    issues.append(tmp)

if issues:
    issues_df = pd.concat(issues, ignore_index=True)
    st.warning(f"Found {len(issues_df)} data quality issues")
    st.dataframe(issues_df, use_container_width=True)
else:
    st.success("No data quality issues found.")

# ---------- INSIGHTS SUMMARY ----------
st.subheader("📝 RevOps Insights Summary")
st.markdown("""
*(Draft — edit this block with your own read of the numbers before submitting)*

- Overall win rate across all closed deals is roughly **XX%**, driven mainly by
  [strongest country/source] which converts noticeably above average.
- [Weakest country/CRM] shows the lowest win rate, suggesting either a poor
  ICP fit or a process bottleneck worth investigating with the sales team.
- Deals sourced from **[top source]** make up the largest volume, but their
  win rate is [higher/lower] than average — worth checking if that channel
  needs better lead qualification upstream.
- Higher PPC budget tiers [do/do not] correlate with better win rates, which
  [supports/questions] the assumption that bigger ad spend brings
  higher-intent leads.
- The data quality table above surfaced **{n_issues} issues**, mostly
  [closed deals missing a Closing Date / missing loss reasons] — fixing this
  at the CRM validation-rule level would improve reporting accuracy going
  forward.
""".format(n_issues=len(issues_df) if issues else 0))
