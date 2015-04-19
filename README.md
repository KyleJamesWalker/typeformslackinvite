TypeForm Slack Invite Script
============================
Small cronjob script to allow anyone to sign up to a slack organization.

Example Usage:

  1. pip install requirements.txt
  2. Create settings.yaml in the same folder as invite.py and fill out the
     required values (null values from defaults.yaml)
  3. Run python invite.py

Multiple Organizations:

  1. Create settings.yaml with multiple top level keys.
  2. Run python invite.py example

  Example settings.yaml:

  ``` yaml
  # Default selected without params.
  invites:
    typeform:
      uuid: xxxx
      api_key: xxxx
    slack:
      organization: default
      token: xxxx
  logging_config: &logging
    handlers:
      email:
        fromaddr: gmail_user@gmail.com
        toaddrs: [your_admins@anywhere.com]
        credentials: [gmail_user@gmail.com, gmail_password_for_your_sending_account]
    root:
      handlers: [console, email]
  example:
    typeform:
      uuid: yyyy
      api_key: yyyy
      # Plan on running every half hour (plus some overlap)
      mins_back: 31
    slack:
      organization: power-examples
      token: yyyy
  logging_config: *logging
  alternate:
    typeform:
      uuid: zzzz
      api_key: zzzz
      # Plan on running everyday (plus some overlap)
      mins_back: 1450
    slack:
      organization: yet-another-slack-org
      token: zzzz
  logging_config: *logging
  ```
