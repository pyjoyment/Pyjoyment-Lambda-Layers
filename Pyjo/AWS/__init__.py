"""
Pyjo.AWS - Amazon Web Services for Pyjoyment
============================================
::

    import Pyjo.AWS.SigV4
    import Pyjo.UserAgent

    signer = Pyjo.AWS.SigV4.new(service='lambda', region='eu-central-1')
    ua = Pyjo.UserAgent.new()
    ua.on('start', lambda ua, tx: signer.sign(tx.req))
    print(ua.get('https://lambda.eu-central-1.amazonaws.com/2018-10-31/layers').result.json())

:mod:`Pyjo.AWS` is the namespace of the APIs of Amazon Web Services for
:mod:`Pyjoyment`, which :mod:`Pyjo.UserAgent` calls, without an SDK:
:mod:`Pyjo.AWS.SigV4` signs its requests.

See also
--------

:mod:`Pyjo.AWS.SigV4`, :mod:`Pyjo.UserAgent`.
"""
