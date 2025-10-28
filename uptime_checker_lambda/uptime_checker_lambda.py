import json
import boto3
import os
import requests
import tweepy  # This library supports both v1.1 and v2
from textblob import TextBlob

# --- Environment Variables ---
# IMPORTANT: You must get the BEARER_TOKEN from your Twitter/X Developer Portal
# It's in the same "Keys and Tokens" section as your other keys.
BEARER_TOKEN = os.environ.get('TWITTER_BEARER_TOKEN')

# --- AWS Service Clients ---
IS_SAM_LOCAL = os.environ.get('AWS_SAM_LOCAL')
if IS_SAM_LOCAL:
    print("SAM Local detected: Connecting to local DynamoDB at http://host.docker.internal:8000")
    dynamodb = boto3.resource('dynamodb', endpoint_url='http://host.docker.internal:8000')
else:
    print("Running in AWS: Connecting to default DynamoDB endpoint.")
    dynamodb = boto3.resource('dynamodb')

sns = boto3.client('sns')
TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

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
    
    # Initialize the Tweepy Client for Twitter API v2
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
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=f"Website Down Alert: {website_url} is unreachable.",
                    Subject="Website Down Alert!"
                )

        # 2. Analyze Twitter Sentiment using API v2
        total_sentiment = 0.0
        tweet_count = 0
        try:
            # Use the v2 endpoint for searching recent tweets
            # The `-is:retweet` part filters out retweets for better sentiment accuracy
            query = f'{twitter_keyword} -is:retweet'
            response = twitter_client.search_recent_tweets(query, max_results=10)
            
            # The v2 response object is different. Tweets are in the `data` attribute.
            if response.data:
                for tweet in response.data:
                    total_sentiment += get_sentiment(tweet.text)
                    tweet_count += 1
            else:
                print(f"No tweets found for keyword: {twitter_keyword}")

        except Exception as e:
            print(f"Error fetching tweets for {twitter_keyword}: {e}")

        average_sentiment = total_sentiment / tweet_count if tweet_count > 0 else 0.0

        # 3. Update DynamoDB
        table.update_item(
            Key={'website_url': website_url},
            UpdateExpression="set #st = :s, sentiment_score = :sent",
            ExpressionAttributeNames={'#st': 'status'},
            ExpressionAttributeValues={
                ':s': current_status,
                ':sent': str(round(average_sentiment, 4))
            }
        )
        print(f"Updated {website_url}: Status - {current_status}, Sentiment - {average_sentiment:.4f}")

    return {
        'statusCode': 200,
        'body': json.dumps('Website checks and sentiment analysis complete!')
    }