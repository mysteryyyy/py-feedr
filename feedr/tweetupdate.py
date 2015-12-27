import urllib.error
import urllib.parse
import urllib.request
import traceback
from collections import OrderedDict
from pprint import pprint

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
        self.msg = OrderedDict((
            ('title', ''),
            ('url', ''),
            ('summary', ''),
            ('img_url', ''),
        ))

    def reset_msg(self):
        for key in self.msg:
            self.msg[key] = ''

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
        '''
        Combine the elements in msg into a string.
        Add '\n' between each element.
        '''

        return '\n'.join(filter(bool, self.msg.values()))

    def msg_length(self):
        '''
        Get the length of the msg to be sent as a tweet.
        '''

        return len(self.msg_to_string())

    def get_msg_limit_length_and_urls(self, feed_entry):
        '''
        Calculating the limit length of current tweet
        and returns the url and img_url for cram_the_msg()
        '''

        TWEET_URL_LENGTH = 24
        TWEET_IMG_LENGTH = 25
        msg_limit_length = 140

        try:
            url = feed_entry['link']
        except:
            url = ''
        if url:
            msg_limit_length -= TWEET_URL_LENGTH

        try:
            img_url = self.get_entry_img_url(feed_entry)
        except:
            img_url = ''
        if img_url:
            msg_limit_length -= TWEET_IMG_LENGTH

        return msg_limit_length, url, img_url

    def cram_the_msg(self, feed_entry, msg_limit_length, url, img_url):
        '''
        Cram the contents in msg by calculating the limit length of a tweet.
        '''

        try:
            self.msg['title'] = feed_entry['title'].strip()
        except:
            pass
        else:
            if self.msg_length() > msg_limit_length:
                self.msg['title'] = self.msg['title'][:msg_limit_length]

        try:
            soup = BeautifulSoup(feed_entry['summary'], 'html.parser')
            self.msg['summary'] = ' '.join(
                map(str.strip, soup.get_text().split('\n'))
            ).strip()
        except:
            pass
        else:
            if self.msg_length() > msg_limit_length:
                print('msg({} chars) is longer than {}.'.format(
                    self.msg_length(), msg_limit_length
                ))
                print('summary before trimmed:\n{}'.format(
                    self.msg['summary']
                ))

                index_trimmed = msg_limit_length - self.msg_length()
                self.msg['summary'] = self.msg['summary'][:index_trimmed]

                print('summary after trimmed:\n{}'.format(self.msg['summary']))
                print('trimmed msg: {} chars.'.format(self.msg_length()))

        self.msg['url'] = url
        self.msg['img_url'] = img_url

    def tweet_with_media(self):
        '''
        Send a tweet with image.
        Try to retrieve the image first,
        then remove the img_url in msg and tweet with the image.
        If fail in uploading, add back the img_url into msg
        and tweet with img_url only.
        '''

        try:    # retrieve the image
            tempfile, headers = urllib.request.urlretrieve(self.msg['img_url'])
        except TypeError:
            pprint('img_url is None, tweet with media url.')
            raise
        except urllib.error.URLError:
            pprint('Error while urlretrieving media, tweet with media url.')
            raise

        with open(tempfile, 'rb') as imgfile:
            img = imgfile.read()

        urllib.request.urlcleanup()
        img_url = self.msg.pop('img_url')
        params = {
            'status': self.msg_to_string(),
            'media[]': img,
        }
        try:
            return self.twitter_api.statuses.update_with_media(**params)
        except api.TwitterHTTPError:
            pprint('Cannot tweet with media, tweet with media url.')
            del img
            self.msg['img_url'] = img_url
            raise
        except:
            traceback.print_exc()

    def tweet_with_no_media(self):
        '''
        Send a pure text tweet.
        '''

        try:
            return self.twitter_api.statuses.update(
                status=self.msg_to_string()
            )
        except api.TwitterHTTPError as e:
            pprint(self.msg_length())
            pprint(self.msg)
            pprint("Cannot send this tweet.")
            pprint(e)
        except:
            traceback.print_exc()

    def tweet_latest_update(self, feed_entry):
        '''
        Tweets the latest update, logs when doing so.
        '''

        msg_limit_length, url, img_url = self.get_msg_limit_length_and_urls(
            feed_entry
        )
        self.cram_the_msg(feed_entry, msg_limit_length, url, img_url)

        try:
            self.tweet_with_media()
        except (TypeError, urllib.error.URLError, api.TwitterHTTPError):
            self.tweet_with_no_media()
        except:
            traceback.print_exc()
