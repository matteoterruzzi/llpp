# llpp

[![Python package](https://github.com/matteoterruzzi/llpp/actions/workflows/python-package.yml/badge.svg)](https://github.com/matteoterruzzi/llpp/actions/workflows/python-package.yml)

I initially wanted to call it "Flyweight Local-Origin Plotter", but the acronym didn't sound promising.

This is a weekend project that I wanted to delve in to accomplish some different desires,
some of them related to experimenting in building software products with few, countable features,
less of them related to some actual utility.
This may also be a proof-of-concept of a tool for application performance monitoring 
for a particular/unexpected situation where:

* monitoring was not actually a priority (so I was expected to allocate zero resources to the monitoring itself)
* the web server technology used by the application didn't easily allow to send asynchronous messages to a monitoring service without affecting the application response time.


## Characteristics

So here is Lightweight Local Performance Plotter and you can count its features:

* Implement an extremely simple, unidirectional UDP protocol to write messages in 1 line of code and send them in less than 10 lines of code
* Reliably store consolidated series in a small and fast db, referring to application-specific named stations
* Plot current and historical performance numbers with live updates
* Be very easy on dependencies: you just need standard Python 3 + websockets
* Be production-ready and be safe from unexpected side-effects that can come from integrating tools like this.


## Rationale

Think of llpp as a collector to offload async telemetry messages from your own application server.
This is little more than your usual log files, yet it's more (plotting is certainly not a feature of your log file).
The choice of the UDP protocol is to cut away the 3-way handshake of TCP and keep the overhead to the bare minimum.
Then llpp may eventually itself offload all the data to something else, if you want.
llpp is so simple that you can take it as a template project for a building block of a larger deployment.
For example, you may typically have some remote, central monitoring server which may offer much more features, 
like authorization/authentication, some GUI, advanced filters and queries...


## Direction

This project wants to optimize for simplicity and performance at local scale, hence the name.
Remote operation is out of scope, so is encryption and other non-requirements for this tool.
Ease of understandability of the source code conveys greater utility to llpp.
The source of the server, excluding only tests and plotting, fits in 200 lines of code.


#### To do list:

- [x] Abstract LogHandler interface
- [x] Listen for UDP messages
- [x] Show messages for debug (PrintLogHandler)
- [x] Store consolidated metrics (SqliteLogHandler)
- [x] Serve live metrics updates (WsLogHandler)
- [x] List stations and past metrics (ReadableSqliteLogHandler)
- [x] Serve list of stations and past metrics (WsLogHandler again)
- [ ] Refactor above point as a subclass
- [x] Plot past data using plotly.com/javascript
- [ ] Client-side data aggregation and live update of the plots
- [ ] Serve index.html
- [x] Don't write a usage guide

