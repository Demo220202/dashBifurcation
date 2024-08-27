import json
import re
import boto3
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Update CloudWatch dashboards by brand range.')
parser.add_argument('--aws-access-key-id', required=True, help='AWS Access Key ID')
parser.add_argument('--aws-secret-access-key', required=True, help='AWS Secret Access Key')
parser.add_argument('--region-name', default='us-west-2', help='AWS Region Name')
parser.add_argument('--dashboard-name', required=True, help='Original Dashboard Name')
parser.add_argument('--ranges', required=True, help='Comma-separated brand ranges (e.g., l-m,n-p)')


args = parser.parse_args()

org_dashboard_name = args.dashboard_name

# Initialize boto3 client for CloudWatch
try:
    # Initialize boto3 client for CloudWatch
    cloudwatch_client = boto3.client(
        'cloudwatch',
        region_name=args.region_name,
        aws_access_key_id=args.aws_access_key_id,
        aws_secret_access_key=args.aws_secret_access_key
    )
except Exception as e:
    print(f"Error initializing boto3 client: {e}")
    sys.exit(1)

# Lists to store widgets for each new dashboard
widgets_by_range = {}

# Define the brand ranges
def filter_brands(brands, start, end):
    return [brand for brand in brands if start <= brand[0].lower() <= end]

# Function to update widgets based on brand ranges and fetch the dashboard body
def update_widgets_by_range(dashboard_name, ranges):
    for start, end in ranges:
        range_key = f"{start.upper()}_to_{end.upper()}"
        widgets_by_range[range_key] = []

        response = cloudwatch_client.get_dashboard(DashboardName=dashboard_name)
        dashboard_body = json.loads(response['DashboardBody'])
        widgets = dashboard_body.get('widgets', [])

        for widget in widgets:
            properties = widget.get('properties', {})
            query = properties.get('query', '')

            all_matches = list(re.finditer(r"(PhpAppLogs_([a-zA-Z0-9_-]+)\.zenarate\.com)", query))

            if all_matches:
                last_match = all_matches[-1]
                last_brand = last_match.group(2)
                remaining_query = query[last_match.end():]

                brands = [match.group(2) for match in all_matches]
                unique_brands = sorted(set(brands))

                filtered_brands = filter_brands(unique_brands, start, end)

                query_filtered = ' | '.join(f"SOURCE 'PhpAppLogs_{brand.lower()}.zenarate.com'" for brand in filtered_brands)

                if filtered_brands:
                    new_widget = widget.copy()
                    new_widget['properties']['query'] = f"{query_filtered}{remaining_query}"
                    widgets_by_range[range_key].append(new_widget)

# Function to create a new dashboard with the specified widgets
def create_dashboard(dashboard_name, widgets):
    new_dashboard_body = {
        'widgets': widgets
    }
    response = cloudwatch_client.put_dashboard(
        DashboardName=dashboard_name,
        DashboardBody=json.dumps(new_dashboard_body)
    )
    return response

# Convert the input ranges to a list of tuples
ranges = [tuple(r.split('-')) for r in args.ranges.split(',')]

# Update widgets for each dashboard range
update_widgets_by_range(org_dashboard_name, ranges)

# Create the new dashboards for each range
for start, end in ranges:
    range_key = f"{start.upper()}_to_{end.upper()}"
    dashboard_name = f"Zen_Error_Analysis_{range_key}"
    response = create_dashboard(dashboard_name, widgets_by_range[range_key])
    print(f"Dashboard {dashboard_name} creation response:", response)

# Output the widgets for debugging
for range_key, widgets in widgets_by_range.items():
    print(f"\nWidgets {range_key.replace('_', ' to ')}:")
    print(json.dumps(widgets, indent=2))
