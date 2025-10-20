import json
import boto3
import os
import requests
import tweepy # You will need to create a deployment package with this library
from textblob import TextBlob # You will need to create a deployment package with this library

# --- AWS Service Clients ---
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# --- Environment Variables ---
TABLE_NAME = os.environ.get('DYNAMODB_TABLE')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
# --- Twitter API Credentials (store as environment variables) ---
TWITTER_CONSUMER_KEY = os.environ.get('TWITTER_CONSUMER_KEY')
TWITTER_CONSUMER_SECRET = os.environ.get('TWITTER_CONSUMER_SECRET')
TWITTER_ACCESS_TOKEN = os.environ.get('TWITTER_ACCESS_TOKEN')
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get('TWITTER_ACCESS_TOKEN_SECRET')


def get_twitter_api():
    """Authenticates with Twitter and returns an API object."""
    auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    return tweepy.API(auth)

def get_sentiment(text):
    """Analyzes the sentiment of a given text."""
    analysis = TextBlob(text)
    return analysis.sentiment.polarity

def handler(event, context):
    """
    Lambda handler function to check website status and analyze Twitter sentiment.
    """
    table = dynamodb.Table(TABLE_NAME)
    websites = table.scan().get('Items', [])
    twitter_api = get_twitter_api()

    for site in websites:
        website_url = site['website_url']
        twitter_keyword = site['twitter_keyword']
        current_status = 'DOWN' # Default to DOWN
        
        # 1. Check Website Uptime
        try:
            response = requests.get(website_url, timeout=5)
            if 200 <= response.status_code < 300:
                current_status = 'UP'
        except requests.exceptions.RequestException as e:
            print(f"Error checking {website_url}: {e}")
            # If status changes to DOWN, send a notification
            if site.get('status') != 'DOWN':
                 sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=f"Website Down Alert: {website_url} is unreachable.",
                    Subject="Website Down Alert!"
                )


        # 2. Analyze Twitter Sentiment
        total_sentiment = 0
        tweet_count = 0
        try:
            tweets = twitter_api.search_tweets(q=twitter_keyword, lang="en", count=10)
            for tweet in tweets:
                total_sentiment += get_sentiment(tweet.text)
                tweet_count += 1
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
