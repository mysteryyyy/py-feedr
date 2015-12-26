import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

from bs4 import BeautifulSoup
from html2text import html2text
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

            try:
                return img_tag['src']
            except KeyError:
                print(img_tag)
                print("This <img> tag has no <src>")
                return None

    def tweet_latest_update(self, feed_entry):
        '''
        Tweets the latest update, logs when doing so.
        '''

        msg_limit_length = 140
        TWEET_URL_LENGTH = 24
        TWEET_IMG_LENGTH = 25

        url = feed_entry['link']
        if url:
            msg_limit_length -= TWEET_URL_LENGTH

        img_url = self.get_entry_img_url(feed_entry)
        if img_url:
            msg_limit_length -= TWEET_IMG_LENGTH

        msg = OrderedDict((
            ('title', None),
            ('url', None),
            ('summary', None),
            ('img_url', None),
        ))

        def msg_length():
            return len('\n'.join(filter(bool, msg.values())))

        msg['title'] = feed_entry['title'].strip()
        if msg_length() - msg_limit_length > 0:
            msg['title'] = '{}{}'.format(
                msg['title'][:msg_limit_length - 3],
                '.'*3,
            )

        elif 'summary' in feed_entry:
            msg['summary'] = html2text(feed_entry['summary']).strip()

            if msg_length() - msg_limit_length > 0:
                summary_length = msg_limit_length - msg_length()

                stripped_summary = '{}{}'.format(
                    msg['summary'][:summary_length - 3],
                    '.'*3,
                )
                msg['summary'] = stripped_summary

        print(msg_length())
        print('\n'.join(filter(bool, msg.values())))
        msg['url'] = url

        img_url_splited = urllib.parse.urlsplit(img_url)
        img_url = img_url_splited._replace(
            netloc=urllib.parse.quote(img_url_splited.netloc),
            path=urllib.parse.quote(img_url_splited.path),
        ).geturl()

        try:
            tempfile, headers = urllib.request.urlretrieve(img_url)
        except TypeError:
            pass    # img_url is None
        except urllib.error.URLError:
            print('Error while urlretrieving media, tweet with media url.')
            msg['img_url'] = img_url
        else:
            with open(tempfile, 'rb') as imgfile:
                img = imgfile.read()

            urllib.request.urlcleanup()
            params = {
                'status': '\n'.join(filter(bool, msg.values())),
                'media[]': img,
            }

            try:
                return self.twitter_api.statuses.update_with_media(**params)
            except api.TwitterHTTPError:
                print('Cannot tweet with media, tweet with media url.')
                msg['img_url'] = img_url

        try:
            return self.twitter_api.statuses.update(
                status='\n'.join(filter(bool, msg.values()))
            )
        except api.TwitterHTTPError:
            msg.pop('summary')
            print(msg_length())
            print('\n'.join(filter(bool, msg.values())))
            return self.twitter_api.statuses.update(
                status='\n'.join(filter(bool, msg.values()))
            )
