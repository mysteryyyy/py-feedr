import urllib.request

from bs4 import BeautifulSoup
from twitter import Twitter, OAuth, api


class TweetUpdate(object):

    '''
    This class is used to tweet the latest update from a RSS feed, once that
    update has been handled by the MonitorFeedUpdate object.
    '''

    def __init__(self, oauth_key, oauth_secret, consumer_key, consumer_secret):
        '''
        Initializes a Twitter object from the twitter module, using the given
        API credentials.
        '''

        # Twitter object
        self.twitter_api = Twitter(auth=OAuth(oauth_key, oauth_secret,
                                              consumer_key, consumer_secret))

    def delete_last_tweet(self):
        '''
        Deletes the last tweet in the timeline.
        This method is only called when an element in the feed is modified.
        '''

        last_tweet = self.twitter_api.statuses.home_timeline(count=1)[0]
        return self.twitter_api.statuses.destroy(id=last_tweet['id'])

    def get_entry_img_url(self, feed_entry):
        '''
        If feed entry has <img> then return the url of the image,
        else return None
        '''

        if hasattr(feed_entry, 'content'):
            entry_html = feed_entry.content[0].value
        elif hasattr(feed_entry, 'description'):
            entry_html = feed_entry.description
        else:
            entry_html = None

        if entry_html:
            soup = BeautifulSoup(entry_html, 'html.parser')
            img_tag = soup.find('img')

            if img_tag:
                return img_tag['src']
            else:
                return None

    def tweet_latest_update(self, feed_entry):
        '''
        Tweets the latest update, logs when doing so.
        '''

        msg_limit_length = 140
        TWEET_URL_LENGTH = 23
        TWEET_IMG_LENGTH = 24

        url = feed_entry['link']
        if url:
            msg_limit_length -= TWEET_URL_LENGTH

        img_url = self.get_entry_img_url(feed_entry)
        if img_url:
            msg_limit_length -= TWEET_IMG_LENGTH

        msg = '{}\n'.format(feed_entry['title'])
        if len(msg) - msg_limit_length > 0:
            stripped_title = feed_entry['title'][:msg_limit_length - 3] + '...'
            msg = '{}\n'.format(stripped_title)
        msg += url

        if img_url:
            tempfile, headers = urllib.request.urlretrieve(img_url)
            with open(tempfile, 'rb') as imgfile:
                img = imgfile.read()

            urllib.request.urlcleanup()
            params = {'status': msg, 'media[]': img}

            try:
                return self.twitter_api.statuses.update_with_media(**params)
            except api.TwitterHTTPError as e:
                print('Error: ', e)
                print('Tweet without media.')

        return self.twitter_api.statuses.update(status=msg)
