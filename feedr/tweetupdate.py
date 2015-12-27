import urllib.error
import urllib.parse
import urllib.request
import traceback
from collections import OrderedDict
from pprint import pprint

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
        self.msg = OrderedDict((
            ('title', ''),
            ('url', ''),
            ('summary', ''),
            ('img_url', ''),
        ))

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
            return None

        soup = BeautifulSoup(entry_html, 'html.parser')
        img_tag = soup.find('img')
        try:
            img_url = img_tag['src']
        except KeyError:
            pprint(img_tag)
            pprint("This <img> tag has no <src>")
            return None
        except TypeError:   # entry_html doesn't have <img> tag
            return None
        else:
            img_url_splited = urllib.parse.urlsplit(img_url)
            img_url = img_url_splited._replace(
                netloc=urllib.parse.quote(img_url_splited.netloc),
                path=urllib.parse.quote(img_url_splited.path),
            ).geturl()
            return img_url

    def msg_to_string(self):
        return '\n'.join(filter(bool, self.msg.values()))

    def msg_length(self):
        return len(self.msg_to_string())

    def get_msg_limit_length_and_set_urls(self, feed_entry):
        TWEET_URL_LENGTH = 24
        TWEET_IMG_LENGTH = 25
        msg_limit_length = 140

        try:
            url = feed_entry['link']
        except:
            pass
        else:
            msg_limit_length -= TWEET_URL_LENGTH
            self.msg['url'] = url

        try:
            img_url = self.get_entry_img_url(feed_entry)
        except:
            pass
        else:
            msg_limit_length -= TWEET_IMG_LENGTH
            self.msg['img_url'] = img_url

        return msg_limit_length

    def cram_the_msg(self, feed_entry, msg_limit_length):
        try:
            self.msg['title'] = feed_entry['title'].strip()
        except:
            pass
        if self.msg_length() > msg_limit_length:
            self.msg['title'] = self.msg['title'][:msg_limit_length]

        try:
            self.msg['summary'] = html2text(feed_entry['summary']).strip()
        except:
            pass
        if self.msg_length() > msg_limit_length:
            trimmed_summary_index = msg_limit_length - self.msg_length()
            self.msg['summary'] = self.msg['summary'][:trimmed_summary_index]

        pprint(self.msg_length())
        pprint(self.msg)

    def tweet_with_no_media(self):
        try:
            return self.twitter_api.statuses.update(
                status=self.msg_to_string()
            )
        except api.TwitterHTTPError:
            pprint("Maybe message is too long, remove summary")
            self.msg.pop('summary')
            pprint(self.msg_length())
            pprint(self.msg)
            return self.twitter_api.statuses.update(
                status=self.msg_to_string()
            )
        except:
            traceback.print_exc()

    def tweet_with_media(self):
        try:
            tempfile, headers = urllib.request.urlretrieve(self.msg['img_url'])
        except TypeError:
            pprint('img_url is None, tweet with media url.')
            raise
        except urllib.error.URLError:
            pprint('Error while urlretrieving media, tweet with media url.')
            raise
        else:
            with open(tempfile, 'rb') as imgfile:
                img = imgfile.read()

            urllib.request.urlcleanup()
            params = {
                'status': self.msg_to_string(),
                'media[]': img,
            }

            try:
                return self.twitter_api.statuses.update_with_media(**params)
            except api.TwitterHTTPError:
                pprint('Cannot tweet with media, tweet with media url.')
                raise
            except:
                traceback.print_exc()

    def tweet_latest_update(self, feed_entry):
        '''
        Tweets the latest update, logs when doing so.
        '''

        msg_limit_length = self.get_msg_limit_length_and_set_urls(feed_entry)
        self.cram_the_msg(feed_entry, msg_limit_length)
        try:
            self.tweet_with_media()
        except (TypeError, urllib.error.URLError, api.TwitterHTTPError):
            self.tweet_with_no_media()
        except:
            traceback.print_exc()
