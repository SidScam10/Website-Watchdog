import json
import boto3
import os
import requests
import tweepy
from textblob import TextBlob
from datetime import datetime
import time

# --- AWS Service Clients ---
IS_SAM_LOCAL = os.environ.get('AWS_SAM_LOCAL')
if IS_SAM_LOCAL:
    print("SAM Local detected: Connecting to local DynamoDB at http://host.docker.internal:8000")
    dynamodb = boto3.resource('dynamodb', endpoint_url='http://host.docker.internal:8000')
else:
    print("Running in AWS: Connecting to default DynamoDB endpoint.")
    dynamodb = boto3.resource('dynamodb')

# --- Environment Variables ---
BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")
TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

sns = boto3.client('sns')

def get_sentiment(text):
    """Analyzes the sentiment of a given text."""
    analysis = TextBlob(text)
    return analysis.sentiment.polarity

def handler(event, context):
    """
    Lambda handler function to check website status and analyze Twitter sentiment using API v2.
    """
    table = dynamodb.Table(TABLE_NAME)
    websites = table.scan().get('Items', [])
    
    # --- DEBUG LINE ---
    print(f"--- DEBUG: Loaded Bearer Token: '{BEARER_TOKEN}' ---")
    
    # Initialize the Tweepy Client for Twitter API v2
    if not BEARER_TOKEN:
        print("FATAL ERROR: TWITTER_BEARER_TOKEN environment variable not set.")
        return {'statusCode': 500, 'body': json.dumps('Twitter Bearer Token not configured.')}
        
    try:
        twitter_client = tweepy.Client(BEARER_TOKEN)
    except Exception as e:
        print(f"Error initializing Twitter client: {e}")
        return {'statusCode': 500, 'body': json.dumps('Failed to init Twitter client.')}

    for site in websites:
        website_url = site['website_url']
        twitter_keyword = site['twitter_keyword']
        current_status = 'DOWN'  # Default to DOWN

        # 1. Check Website Uptime
        try:
            response = requests.get(website_url, timeout=10)
            if 200 <= response.status_code < 300:
                current_status = 'UP'
        except requests.exceptions.RequestException as e:
            print(f"Error checking {website_url}: {e}")
            if site.get('status') != 'DOWN':
                # Only publish if the status *changed* to DOWN
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=f"Website Down Alert: {website_url} is unreachable.",
                    Subject="Website Down Alert!"
                )

        # 2. Analyze Twitter Sentiment using API v2
        total_sentiment = 0.0
        tweet_count = 0
        all_tweets = []  # NEW: Create a list to hold example tweets

        try:
            query = f'{twitter_keyword} -is:retweet'
            response = twitter_client.search_recent_tweets(query, max_results=10)
            
            if response.data:
                for tweet in response.data:
                    total_sentiment += get_sentiment(tweet.text)
                    tweet_count += 1
                    # --- NEW: Collect ALL 10 tweets ---
                    all_tweets.append(tweet.text)
            else:
                print(f"No tweets found for keyword: {twitter_keyword}")

        except Exception as e:
            print(f"Error fetching tweets for {twitter_keyword}: {e}")

        average_sentiment = total_sentiment / tweet_count if tweet_count > 0 else 0.0

        new_history_entry = {
            'timestamp': datetime.utcnow().isoformat(), # Add a timestamp
            'sentiment': str(round(average_sentiment, 4)),
            'tweets': all_tweets # Add all 10 tweets
        }

        # 3. Update DynamoDB
        table.update_item(
            Key={'website_url': website_url},
            # --- UPDATED: New UpdateExpression ---
            UpdateExpression="set #st = :s, sentiment_score = :sent, " + \
                             "example_tweets = :t, " + \
                             "tweet_history = list_append(if_not_exists(tweet_history, :empty_list), :h)",
            ExpressionAttributeNames={'#st': 'status'},
            # --- UPDATED: New ExpressionAttributeValues ---
            ExpressionAttributeValues={
                ':s': current_status,
                ':sent': str(round(average_sentiment, 4)),
                ':t': all_tweets[:3],  # Keep example_tweets as the first 3
                ':h': [new_history_entry],    # Append the new history entry as a list
                ':empty_list': []             # Create an empty list if tweet_history doesn't exist
            }
        )
        print(f"Updated {website_url}: Status - {current_status}, Sentiment - {average_sentiment:.4f}")

        # Add a 10-second delay to respect Twitter's rate limit
        print("Waiting 10 seconds to avoid rate limit...")
        time.sleep(10)

    return {
        'statusCode': 200,
        'body': json.dumps('Website checks and sentiment analysis complete!')
    }