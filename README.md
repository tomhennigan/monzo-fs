# mondo-fs

mondo-fs is a [FUSE](https://github.com/libfuse/libfuse) file system that allows you to walk through a [Mondo](http://getmondo.co.uk) account and associated transactions as if they were files and folders.

mondo-fs is:

* **alpha quality**: it works for me but ymmv, it might break as Mondo change their API or for other random reasons.
* **simple**: it roughly follows the Mondo API's structure to make your account easy to navigate.
* **powerful**: using the shell tools you know and love you can slice and dice all the information from your Mondo account and create compelling demos.
* **read only**: this is not a huge limitation *imho*, and not something I'm likely to address in the near future, but being able to upload receipt images with drag-and-drop would be neat.
* **a personal project**: this is not something related to my professional employment, or something I have copious time to work on and extend.

mondo-fs builds upon the [Mondo API](https://getmondo.co.uk/docs/), and makes use of some other excellent open source projects such as (but not limited to) [fusepy](https://github.com/terencehonles/fusepy), [FUSE](https://github.com/libfuse/libfuse), [rfc3339](https://pypi.python.org/pypi/rfc3339) and [iso8601](https://pypi.python.org/pypi/iso8601) libraries.

## Getting started

You will first need to install FUSE. Mac users `brew install fuse` is an easy option, Linux users should enjoy something as simple as `apt-get install fuse` and I have no idea how this (or anything) works on Windows.

Once you have fuse installed:

1. Create a [Mondo developer account](https://developers.getmondo.co.uk/).
2. Create a [new oauth client](https://developers.getmondo.co.uk/apps/new) with `http://localhost:1234/` listed as a "Redirect URL". Note the client id and secret (you need them later).
3. Install mondo-fs: `$ pip install mondo-fs`
4. Run mondo-fs: `$ mondo-fs /tmp/mondo --client_id=<yours> --client_secret=<yours>`.
5. Run through the oauth dance (click the link in terminal, put in your email, click the link in your email, go back to terminal).
6. You're good to go, mondo-fs is mounted on `/tmp/mondo`!

### tl;dr

You need a [Mondo developer account](https://developers.getmondo.co.uk/) and [oauth client](https://developers.getmondo.co.uk/apps/new) with `http://localhost:1234` as a "Redirect URL".

Window 1 (install, mount):

```
$ brew install fuse
$ pip install mondo-fs
$ mondo-fs /tmp/mondo --client_id=<yours> --client_secret=<yours>
# Follow the instructions on screen and then in your browser.
```

Window 2 (explore):

```
$ ls /tmp/mondo
acc_00009Aq4VDixoGFnIxcBmr

$ ls /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/ | head
tx_00009Aq4fq7rt647A5pWLp
tx_00009Aq6sLNlhcLnU9MDar
tx_00009Aq7I54SyEEcv5LaUb
tx_00009Aq8QMKOnDp8DaZ5KD
tx_00009Aq9nVdkRA4XqxiQV7
tx_00009AqFGWd8Knhd5o5EDB
tx_00009AqFXAUHugn7U6PiLZ
tx_00009AqFxqpP7AZZH3ybb7
tx_00009AqFxyKrCcmLc8meOH
tx_00009AqG0e3D4pITZTntvl

$ ls /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/
account_balance category        dedupe_id       json            metadata        settled
account_id      counterparty    description     local_amount    notes           updated
amount          created         id              local_currency  originator
attachments     currency        is_load         merchant        scheme

$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/category
mondo

$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/amount
100.00

$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/is_load
True
```

## Examples

Some random examples to get you started/excited. Basically it's possible to explore your transaction history in a pretty meaningful way by looking at it as a file system. mondo-fs is designed to be relatively efficient so you don't have to be (e.g. we cache requests) but not overly agressive so data is relatively fresh (e.g. caches live a few minutes for transactions).

### Retrieve your balance

```
$ ls -l /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/balance/
total 24
-r--r--r--  0 root  wheel  6  1 Jan  1970 balance
-r--r--r--  0 root  wheel  4  1 Jan  1970 currency
-r--r--r--  0 root  wheel  7  1 Jan  1970 spend_today

$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/balance/balance
41.44

$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/balance/spend_today
-55.69
```

### Print the notes from a specific transaction

```
$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2015/08/tx_00008zIcpb1TB4yeIFXMzx/notes
Salmon sandwich 🍞
```

### Print the number of transactions per day in a given month

```
$ cat /tmp/mondo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/*/created | cut -d T -f 1 | cut -d - -f 3 | sort | uniq -c
  17 01
   4 02
   4 03
   7 04
   4 05
   7 06
   5 07
   5 08
   1 09
   3 10
   3 11
   5 12
   7 13
   4 14
   1 15
   1 16
   6 17
```

### Print a graph of your spending over a given month

This one needs a shell script to be readable ;)

```sh
#!/bin/sh
for account in "$(ls -1 /tmp/mondo/)"; do
    # For each account...
    
    # 1) Create and truncate a file to hold date/balance pairs.
    touch "/tmp/mondo-balance-${account}"
    > "/tmp/mondo-balance-${account}"

    # 2) Loop through all transactions in 2016/08 and get the created time and balance.
    for txn in "/tmp/mondo/${account}/transactions/2016/08/"*; do
        # Print out "date time balance" records.
        created="$(cat "${txn}/created" | cut -d . -f 1)"
        balance="$(cat "${txn}/account_balance")"
        echo "${created} ${balance}" >> /tmp/mondo-balance-${account}
    done 

    # 3) Plot as a graph using gnuplot.
    gnuplot << __EOF
    set terminal png
    set output '/tmp/mondo-balance-${account}.png'
    set xdata time
    set format x "%m/%d"
    set timefmt "%Y-%m-%dT%H:%M:%S"
    plot "/tmp/mondo-balance-${account}" using 1:2 with linespoints
__EOF

    # 4) Profit?
    rm -f "/tmp/mondo-balance-${account}"
    open /tmp/mondo-balance-${account}.png
done
```
