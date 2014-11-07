import json
import urlparse
import requests

class FreshDeskObjects(object):
    """ Abstract class to wrap a type of freshdesk resource.
    """
    def __init__(self, client):
        self.client = client

    def api_endpoint(self, id=None):
        if id:
            return '/{}s/{}.json'.format(self.api_name, id)
        else:
            return '/{}s.json'.format(self.api_name)

    # CRUD methods

    def create(self, **kwargs):
        return client.req(requests.post, self.api_endpoint(), self.api_name,
                          **kwargs)

    def update(self, id, **kwargs):
        return self.client.req(requests.put, self.api_endpoint(id), self.api_name
                               **kwargs)

    def delete(self, id):
        return self.client.req(
            requests.delete, self.api_endpoint(id), self.api_name)

    def get(self, id):
        return self.client.req(
            requests.get, self.api_endpoint(id), self.api_name, id=id)

    def get_list(self, **params):
        return self.client.req(requests.get, self.api_endpoint(), self.api_name,
                               params=params)


class FreshDeskContacts(FreshDeskObjects):
    """ http://freshdesk.com/api#user
    """
    api_name = 'contact'

    # Status names (default is state=verified)
    DELETED    = 'deleted'
    ALL        = 'all'         # Do not include deleted accounts
    VERIFIED   = 'verified'
    UNVERIFIED = 'unverified'

    def create(self, name, email):
        super(FreshDeskContacts, self).create(name=name, email=email)


class FreshDeskCustomers(FreshDeskObjects):
    """ http://freshdesk.com/api#companies
    """
    api_name = 'customer'

    def create(self, name):
        super(FreshDeskContacts, self).create(name=name)


class FreshDeskClient(object):
    """ Simple wrapper arround freshdesk REST API

    This wrapper is non neutral, it includes Oasiswork policy about default
    settings.

        cli = FreshDeskClient('https://mycompany.freshdesk.com', 'qwertyui')
        cli.contacts.get_list(state='all')

    """
    class APIError(Exception):
        def __init__(resp):
            self.resp = resp
        def __str__(resp):
            return 'HTTP {}: {}'.format(resp.status_code, resp.text)

    def __init__(self, url, key):
        """
        :param url  endpoint url, eg: https://yourcompany.freshdesk.com
        :param key  API key
        """
        self.url = url
        self.key = key
        self.last_resp = None

        # Resources types
        self.customers = FreshDeskCustomers(self)
        self.contacts = FreshDeskContacts(self)

    def req(self, func, path, resource_type, params={}, **kwargs):
        abs_url = urlparse.urljoin(self.url, path)

        if func in (requests.patch, requests.put, requests.post):
            req_attrs = {
                'data': json.dumps({resource_type: kwargs}),
                'headers': {'Content-Type': 'application/json'}
            }
        else:
            req_attrs = {}

        resp =  func(
            abs_url,
            auth=(self.key, 'nopassword'),
            params=params,
            **req_attrs)
        self.last_resp = resp
        if resp.ok:
                return resp.json()

        else:
            raise self.APIError(resp)

