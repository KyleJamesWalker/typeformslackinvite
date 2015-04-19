# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import logging
import logging.config
import logging.handlers
import os
import requests

from time import time
from yamlsettings import YamlSettings

invite_path = os.path.dirname(os.path.realpath(__file__))
settings = None
logger = None


class BufferingSMTPHandler(logging.handlers.BufferingHandler):
    def __init__(self, mailhost=None, fromaddr=None, toaddrs=None,
                 subject=None, capacity=None, credentials=None, secure=None):
        if not all([mailhost, fromaddr, toaddrs, subject, capacity]):
            raise ValueError("The following must be set: mailhost, fromaddr, "
                             "toaddrs, subject, capacity")

        # Get a BufferingHandler
        logging.handlers.BufferingHandler.__init__(self, capacity)

        # Save SMTP Settings
        # From SMTPHandler.__init__()
        if isinstance(mailhost, (tuple, list)):
            self.mailhost, self.mailport = mailhost
        else:
            self.mailhost, self.mailport = mailhost, None
        if isinstance(credentials, (tuple, list)):
            self.username, self.password = credentials
        else:
            self.username = None
        self.fromaddr = fromaddr
        if isinstance(toaddrs, basestring):
            toaddrs = [toaddrs]
        self.toaddrs = toaddrs
        self.subject = subject
        self.secure = secure
        self._timeout = 5.0

    def getSubject(self, record):
        """
        Determine the subject for the email.

        If you want to specify a subject line which is record-dependent,
        override this method.
        """
        return self.subject

    def build_msg(self):
        return "\r\n".join([self.format(x) for x in self.buffer])

    def flush(self):
        """
        Flush records.

        Format the records and send it to the specified addressees.
        """
        if len(self.buffer) > 0:
            try:
                import smtplib
                from email.utils import formatdate
                port = self.mailport
                if not port:
                    port = smtplib.SMTP_PORT
                smtp = smtplib.SMTP(self.mailhost, port, timeout=self._timeout)
                msg = self.build_msg()
                msg = "From: %s\r\nTo: %s\r\n" \
                    "Subject: %s\r\nDate: %s\r\n\r\n%s" % (
                        self.fromaddr,
                        ",".join(self.toaddrs),
                        self.getSubject(self.buffer[0]),
                        formatdate(), msg)
                if self.username:
                    if self.secure is not None:
                        smtp.ehlo()
                        smtp.starttls(*self.secure)
                        smtp.ehlo()
                    smtp.login(self.username, self.password)
                smtp.sendmail(self.fromaddr, self.toaddrs, msg)
                smtp.quit()
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                self.handleError(self.buffer[0])
        self.buffer = []


def slack_invite_dict(first_name=None, last_name=None, email=None):
    '''
        Create dictionary with required information needed for a slack invite.

        :param first_name: Invite's first name
        :param last_name: Invite's last name
        :param email: Invite's email address
    '''
    return dict(
        first_name=first_name,
        last_name=last_name,
        email=email,
    )


def get_typeform_question_ids(questions):
    '''
        Discover the field ids for each of your questions

        :param questions: Questions dictionary from typefrom response
    '''
    for x in questions:
        if 'email address' in x['question'].lower():
            email = x['id']
        elif 'first name' in x['question'].lower():
            first_name = x['id']
        elif 'last name' in x['question'].lower():
            last_name = x['id']

    return slack_invite_dict(first_name, last_name, email)


def get_typeform():
    '''
        Get your typeform responses.  Uses yamlsettings for request.
    '''
    typeform = settings.typeform
    since = None

    if typeform.mins_back:
        logging.debug("Limiting Typeform since {} mins"
                      .format(typeform.mins_back))
        since = int(time()) - (typeform.mins_back * 60)

    form_url = typeform.url.format(uuid=typeform.uuid)
    payload = {
        'completed': typeform.completed,
        'key': typeform.api_key,
        'limit': typeform.resp_limit,
        'offset': 0,
        'since': since,
    }

    invites = []

    while True:
        logging.debug("Requesting Typeform with offset {}".
                      format(payload['offset']))

        r = requests.get(form_url, params=payload)
        if r.status_code is not 200:
            raise ValueError("Invalid Status Code: {}".format(r.status_code))

        results = r.json()

        ids = get_typeform_question_ids(results['questions'])

        if results['responses']:
            for x in results['responses']:
                invite = slack_invite_dict(x['answers'][ids['first_name']],
                                           x['answers'][ids['last_name']],
                                           x['answers'][ids['email']])
                logging.debug('Retrieved "{first_name} {last_name}" <{email}>'.
                             format(**invite))
                invites.append(invite)

            payload['offset'] += payload['limit']
            if len(results['responses']) < payload['limit']:
                break
        else:
            break

    return invites


def parse_slack_response(response):
    '''
        Parse response from undocumented admin invite.

        :param response: Slack's Response to a users.admin.invite
    '''
    return "OK" if response['ok'] is True else response['error']


def slack_invite(invites):
    '''
        Invite Slack Users.

        :param invites: List of invite dictionaries to invite::
            invites = [dict(first_name='Example',
                            last_name='Person',
                            email='example.person@null.net')]
            slack_invite(invites)
    '''
    slack = settings.slack

    param_payload = {
        't': time(),
    }

    data_payload = {
        "token": slack.token,
        "set_active": True,
        "_attempts": 1,
    }

    for x in invites:
        x.update(data_payload)
        r = requests.post(
            slack.url.format(org=slack.organization),
            params=param_payload,
            data=x,
        )
        response = parse_slack_response(r.json())
        logging.info(
            "Invite for '{} {}' <{}> response {}".
            format(x['first_name'],
                   x['last_name'],
                   x['email'],
                   response)
        )

    return invites


def main():
    global settings, logger

    parser = argparse.ArgumentParser(description='TypeFormed Slack Invites')
    parser.add_argument("section", action="store",
                        nargs='?', default='invites',
                        help="Settings Section")

    args = parser.parse_args()

    try:
        settings = YamlSettings(
            '{}/defaults.yaml'.format(invite_path),
            '{}/settings.yaml'.format(invite_path),
            default_section='invites'
        ).get_settings(args.section)
    except KeyError:
        logging.critical("Error: Unable to find section {}, check settings.".
                         format(args.section))
        return None

    logging.config.dictConfig(settings.logging_config)
    logger = logging.getLogger(__name__)

    logging.debug("Inviting New Slack Members")
    invites = get_typeform()
    slack_invite(invites)
    logging.debug("Finished inviting {} members".format(len(invites)))

if __name__ == '__main__':
    main()
