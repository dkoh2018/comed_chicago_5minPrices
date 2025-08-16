

import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import pytz
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def fetch_comed_pricing_data():
    """Fetch 5-minute pricing data from ComEd API"""
    # Use dynamic dates - get data for the last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Format dates for API
    start_str = start_date.strftime("%Y%m%d0000")
    end_str = end_date.strftime("%Y%m%d2359")
    
    url = f"https://hourlypricing.comed.com/api?type=5minutefeed&datestart={start_str}&dateend={end_str}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data, None
    except requests.exceptions.RequestException as e:
        return None, f"Error fetching data: {e}"
    except json.JSONDecodeError as e:
        return None, f"Error parsing JSON response: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"

def convert_to_chicago_time(timestamp_str):
    """Convert timestamp to Chicago timezone"""
    try:
        # Handle millisecond UTC timestamps (like 1753743600000)
        if timestamp_str.isdigit() and len(timestamp_str) == 13:
            # Convert milliseconds to seconds and create datetime
            timestamp_seconds = int(timestamp_str) / 1000
            # Create UTC datetime directly to avoid system timezone issues
            dt = datetime.utcfromtimestamp(timestamp_seconds).replace(tzinfo=pytz.utc)
        elif len(timestamp_str) == 14:  # Format: YYYYMMDDHHMMSS
            dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
        elif len(timestamp_str) == 12:  # Format: YYYYMMDDHHMM
            dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M")
        else:
            # Try ISO format or other common formats
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Set timezone to Chicago
        chicago_tz = pytz.timezone('America/Chicago')
        
        # If the datetime is naive (no timezone), assume it's UTC
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        
        # Convert to Chicago time
        chicago_time = dt.astimezone(chicago_tz)
        return chicago_time
    
    except Exception as e:
        return None

def process_data_for_plotting(data):
    """Process API data into a format suitable for plotting"""
    if not data:
        return None, None, None, "No data received"
    
    # Handle different possible data structures
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # Try different possible keys for the data
        for key in ['data', 'prices', 'feed', 'results', 'items']:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        # If no list found, try to use the dict itself
        if not items:
            items = [data]
    else:
        return None, None, None, f"Unexpected data format: {type(data)}"
    
    # Extract times and prices
    times = []
    prices = []
    
    for item in items:
        if not isinstance(item, dict):
            continue
            
        # Try different possible field names for timestamp and price
        timestamp = None
        price = None
        
        # Look for timestamp fields
        for ts_field in ['millisUTC', 'timestamp', 'time', 'date', 'datetime']:
            if ts_field in item:
                timestamp = item[ts_field]
                break
                
        # Look for price fields
        for price_field in ['price', 'value', 'cost', 'rate']:
            if price_field in item:
                try:
                    price = float(item[price_field])
                    break
                except (ValueError, TypeError):
                    continue
        
        if timestamp and price is not None:
            try:
                chicago_time = convert_to_chicago_time(str(timestamp))
                
                # Filter out invalid prices
                if chicago_time and 0 <= price <= 1000:
                    times.append(chicago_time)
                    prices.append(price)
            except (ValueError, KeyError, Exception):
                continue
    
    if not times or not prices:
        return None, None, None, f"No valid data points found. Processed {len(items)} items."
    
    # Sort by time
    sorted_data = sorted(zip(times, prices))
    times, prices = zip(*sorted_data)
    
    return times, prices, len(items), None

def create_weekly_chart(df, week_start, week_end, week_number, show_average=True, show_median=False):
    """Create a chart for a specific week"""
    # Filter data for this week
    week_data = df[(df['Time'] >= week_start) & (df['Time'] <= week_end)]
    
    if len(week_data) == 0:
        return None, None
    
    if len(week_data) == 0:
        return None, None
    
    # Calculate statistics
    avg_price = week_data['Price'].mean()
    median_price = week_data['Price'].median()
    min_price = week_data['Price'].min()
    max_price = week_data['Price'].max()
    
    # Create the plot
    fig = go.Figure()
    
    # Add the bars
    fig.add_trace(go.Bar(
        x=week_data['Time'],
        y=week_data['Price'],
        name='Price (cents)',
        marker_color='#2E86AB',
        opacity=0.7,
        hovertemplate='<b>Time:</b> %{x}<br><b>Price:</b> %{y:.1f} cents<extra></extra>'
    ))
    
    # Add average line if requested
    if show_average:
        fig.add_hline(
            y=avg_price,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Avg: {avg_price:.1f}¢",
            annotation_position="top right"
        )
    
    # Add median line if requested
    if show_median:
        fig.add_hline(
            y=median_price,
            line_dash="dot",
            line_color="orange",
            annotation_text=f"Med: {median_price:.1f}¢",
            annotation_position="bottom right"
        )
    
    # Format week range for title
    week_start_str = week_start.strftime("%m/%d")
    week_end_str = week_end.strftime("%m/%d")
    
    # Update layout
    fig.update_layout(
        title={
            'text': f'Week {week_number}: {week_start_str} - {week_end_str} | Avg: {avg_price:.1f}¢',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 16, 'color': 'white'}
        },
        xaxis_title="",
        yaxis_title="Price (cents)",
        hovermode='x unified',
        showlegend=False,
        height=300,
        template='plotly_white',
        margin=dict(l=50, r=50, t=50, b=50)
    )
    
    # Update x-axis formatting
    fig.update_xaxes(
        tickformat='%m/%d %H:%M',
        tickangle=45,
        tickmode='auto',
        nticks=10,
        range=[week_start, week_end],
        type='date'
    )
    
    return fig, {
        'avg_price': avg_price,
        'median_price': median_price,
        'min_price': min_price,
        'max_price': max_price,
        'total_points': len(week_data)
    }

def get_week_boundaries(end_date, num_weeks=5):
    """Get the start and end dates for the last N weeks (Sunday to Saturday)"""
    chicago_tz = pytz.timezone('America/Chicago')
    end_date = end_date.replace(tzinfo=chicago_tz)
    
    # Find the most recent Sunday (start of week)
    days_since_sunday = (end_date.weekday() - 6) % 7
    if days_since_sunday == 0:
        # If today is Sunday, use today
        last_sunday = end_date
    else:
        # Go back to the most recent Sunday
        last_sunday = end_date - timedelta(days=days_since_sunday)
    
    # Set to start of Sunday (00:00:00)
    last_sunday = last_sunday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    weeks = []
    for i in range(num_weeks):
        # Start of week (Sunday 00:00:00)
        week_start = last_sunday - timedelta(weeks=i)
        # End of week (Saturday 23:59:59)
        week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
        
        weeks.append((week_start, week_end))
    
    return weeks

def main():
    # Page configuration
    st.set_page_config(
        page_title="ComEd Pricing Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Hide the sidebar completely
    st.markdown("""
        <style>
        [data-testid="collapsedControl"] {
            display: none
        }
        </style>
        """, unsafe_allow_html=True)
    
    # Header
    st.title("⚡ ComEd Pricing Dashboard")
    st.markdown("Real-time electricity pricing from ComEd's Hourly Pricing Program")
    
    # Auto-refresh functionality
    st.markdown("""
        <script>
        // Auto-refresh the page every 5 minutes (300 seconds)
        setTimeout(function(){
            window.location.reload();
        }, 300000);
        </script>
        """, unsafe_allow_html=True)
    
    # Controls section with better organization
    st.markdown("---")
    st.markdown("### ⚙️ Dashboard Controls")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        st.markdown("**🔄 Auto-refresh:** Every 5 minutes")
    with col2:
        line_option = st.radio("**📊 Chart Lines:**", ["None", "Average", "Median"], horizontal=True, index=1)
    with col3:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Convert radio selection to boolean flags
    show_average = line_option == "Average"
    show_median = line_option == "Median"
    
    st.markdown("---")
    
    # Fetch data with shorter cache time for more frequent updates
    @st.cache_data(ttl=300)  # Cache for 5 minutes instead of 1 hour
    def cached_fetch_data():
        return fetch_comed_pricing_data()
    
    # Fetch data
    with st.spinner("Loading pricing data..."):
        data, error = cached_fetch_data()
    
    if error:
        st.error(f"Error fetching data: {error}")
        st.info("Showing sample data for demonstration purposes.")
        
        # Generate sample data for demonstration
        end_time = datetime.now(pytz.timezone('America/Chicago'))
        start_time = end_time - timedelta(days=7)
        
        # Create sample data
        sample_times = []
        sample_prices = []
        current_time = start_time
        
        while current_time <= end_time:
            sample_times.append(current_time)
            # Generate realistic price variations
            base_price = 5.0
            hourly_variation = 2.0 * np.sin(current_time.hour * np.pi / 12)  # Daily cycle
            random_variation = np.random.normal(0, 1.0)
            price = max(0, base_price + hourly_variation + random_variation)
            sample_prices.append(price)
            current_time += timedelta(minutes=5)
        
        times, prices = sample_times, sample_prices
        total_points = len(sample_times)
    else:
        # Process real data
        times, prices, total_points, process_error = process_data_for_plotting(data)
        
        if process_error:
            st.error(process_error)
            return
        
        if not times or not prices:
            st.error("No valid data points found")
            return
    
    # Create DataFrame
    df = pd.DataFrame({
        'Time': times,
        'Price': prices
    })
    
    # Get week boundaries for the last 5 weeks
    week_boundaries = get_week_boundaries(datetime.now(), num_weeks=5)
    
    # Calculate weekly statistics for sidebar comparison
    weekly_stats = []
    for i, (week_start, week_end) in enumerate(week_boundaries):
        week_data = df[(df['Time'] >= week_start) & (df['Time'] <= week_end)]
        
        if len(week_data) > 0:
            week_start_str = week_start.strftime("%m/%d")
            week_end_str = week_end.strftime("%m/%d")
            weekly_stats.append({
                'week': f"Week {i+1}: {week_start_str}-{week_end_str}",
                'avg_price': week_data['Price'].mean(),
                'min_price': week_data['Price'].min(),
                'max_price': week_data['Price'].max(),
                'data_points': len(week_data)
            })
    

    
    # Recent Activity Section
    st.markdown("### 📈 Recent Activity")
    
    if len(df) > 0:
        # Get the last 144 data points (12 hours), sorted by time (newest first)
        recent_data = df.sort_values('Time', ascending=False).head(144)
        
        # Create side-by-side layout
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Create bar chart for the same 144 data points
            if len(recent_data) > 0:
                # Sort by time for proper chart display (oldest to newest)
                chart_data = recent_data.sort_values('Time', ascending=True)
                
                # Calculate average and median for the lines
                avg_price = chart_data['Price'].mean()
                median_price = chart_data['Price'].median()
                
                # Create the bar chart
                fig = go.Figure()
                
                # Add bars
                fig.add_trace(go.Bar(
                    x=chart_data['Time'],
                    y=chart_data['Price'],
                    name='Price (cents)',
                    marker_color='white',
                    marker_line_color='#2E86AB',
                    marker_line_width=1,
                    opacity=1.0,
                    hovertemplate='<b>Time:</b> %{x}<br><b>Price:</b> %{y:.1f} cents<extra></extra>'
                ))
                
                # Add average line
                if show_average:
                    fig.add_hline(
                        y=avg_price,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"Avg: {avg_price:.1f}¢",
                        annotation_position="top right"
                    )
                
                # Add median line
                if show_median:
                    fig.add_hline(
                        y=median_price,
                        line_dash="dot",
                        line_color="orange",
                        annotation_text=f"Med: {median_price:.1f}¢",
                        annotation_position="bottom right"
                    )
                
                # Update layout
                fig.update_layout(
                    title={
                        'text': f'Last 12 Hours | Avg: {avg_price:.1f}¢',
                        'x': 0.5,
                        'xanchor': 'center',
                        'font': {'size': 14, 'color': 'white'}
                    },
                    xaxis_title="Time",
                    yaxis_title="Price (cents)",
                    hovermode='x unified',
                    showlegend=False,
                    height=400,
                    template='plotly_white',
                    margin=dict(l=50, r=50, t=50, b=50)
                )
                
                # Update x-axis formatting
                fig.update_xaxes(
                    tickformat='%m/%d %H:%M',
                    tickangle=45,
                    tickmode='auto',
                    nticks=10
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Create table data
            table_data = []
            for _, row in recent_data.iterrows():
                time_str = row['Time'].strftime('%m/%d %H:%M')
                price_str = f"{row['Price']:.1f}¢"
                table_data.append([time_str, price_str])
            
            # Create DataFrame for table display
            table_df = pd.DataFrame(table_data, columns=['Time', 'Price'])
            st.dataframe(
                table_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Time": st.column_config.TextColumn("Time", width="medium"),
                    "Price": st.column_config.TextColumn("Price", width="small")
                }
            )
    
    st.markdown("---")
    
    # Weekly Analysis Section
    st.markdown("### 📅 Weekly Analysis")
    
    # Create and display weekly charts
    charts_created = 0
    
    for i, (week_start, week_end) in enumerate(week_boundaries):
        fig, stats = create_weekly_chart(df, week_start, week_end, i+1, show_average, show_median)
        
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
            charts_created += 1
            
            # Show data availability info for this week
            week_data_debug = df[(df['Time'] >= week_start) & (df['Time'] <= week_end)]
            if len(week_data_debug) > 0:
                actual_start = week_data_debug['Time'].min()
                actual_end = week_data_debug['Time'].max()
                if actual_start.date() > week_start.date() or actual_end.date() < week_end.date():
                    st.caption(f"Data available: {actual_start.strftime('%m/%d')} - {actual_end.strftime('%m/%d')} (partial week)")
    
    # Footer
    st.markdown("---")
    st.markdown("*Data Source: ComEd Hourly Pricing Program API*")

if __name__ == "__main__":
    main()