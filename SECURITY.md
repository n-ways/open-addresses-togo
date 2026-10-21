# Reporting a problem

Write to **hello@nways.ng**, with "Security" or "Registry" in the subject.

Report there, privately, anything that could harm people or the registry:

- a weakness in the registry server (`server/`): a way to issue or change codes without a valid key, to read the
  keys, to crash or slow a deployment, or to make it answer wrongly;
- a code, a published row or a document that exposes personal information (a resident's name, a phone number, an
  identity number) or puts someone at risk;
- a mismatch between the published registry and its `MANIFEST.json`, or a code that decodes to the wrong place;
- an issuing deployment that the State or N-WAYS LIMITED has not designated.

Please give what is needed to reproduce the problem (the request, the code or the file, and what you expected), and
allow us time to correct it before making it public. We acknowledge reports within three working days and say what
we will do and when. Ordinary corrections (a wrong gate, a spelling) are welcome as public issues
([CONTRIBUTING.md](CONTRIBUTING.md)).

If you run a deployment: keep `ISSUE_KEYS` empty unless you are the designated issuer, serve it only behind TLS, and
keep the server and Python up to date (`server/README.md`).
