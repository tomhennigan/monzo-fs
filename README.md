# monzo-fs

monzo-fs is a [FUSE](https://github.com/libfuse/libfuse) file system that allows you to walk through a [Monzo](http://monzo.com) account and associated transactions as if they were files and folders.

monzo-fs is:

* **alpha quality**: it works for me but ymmv, it might break as Monzo change their API or for other random reasons.
* **simple**: it roughly follows the Monzo API's structure to make your account easy to navigate.
* **powerful**: using the shell tools you know and love you can slice and dice all the information from your Monzo account and create compelling demos.
* **read only**: this is not a huge limitation *imho*, and not something I'm likely to address in the near future, but being able to upload receipt images with drag-and-drop would be neat.
* **a personal project**: this is not something related to my professional employment, or something I have copious time to work on and extend.

monzo-fs builds upon the [Monzo API](https://getmondo.co.uk/docs/), and makes use of some other excellent open source projects such as (but not limited to) [fusepy](https://github.com/terencehonles/fusepy), [FUSE](https://github.com/libfuse/libfuse), [rfc3339](https://pypi.python.org/pypi/rfc3339) and [iso8601](https://pypi.python.org/pypi/iso8601) libraries.

## tl;dr

You need a [Monzo developer account](https://developers.getmondo.co.uk/) and [your own oauth client](https://developers.getmonzo.co.uk/apps/new) with `http://localhost:1234` as a "Redirect URL".

**Terminal 1 (install fuse, install monzo-fs, mount)**

```
$ brew install fuse
$ pip install monzo-fs
$ monzo-fs /tmp/monzo --client_id=<yours> --client_secret=<yours>
.. Follow the instructions on screen and then in your browser ..
```

**Terminal 2 (explore)**

```
$ ls /tmp/monzo
acc_00009Aq4VDixoGFnIxcBmr

$ ls /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/ | head
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

$ ls /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/
account_balance category        dedupe_id       json            metadata        settled
account_id      counterparty    description     local_amount    notes           updated
amount          created         id              local_currency  originator
attachments     currency        is_load         merchant        scheme

$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/category
monzo

$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/amount
100.00

$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/tx_00009Aq4fq7rt647A5pWLp/is_load
True
```

## Getting started

You will first need to install FUSE. Mac users `brew install fuse` is an easy option, Linux users should enjoy something as simple as `apt-get install fuse` and I have no idea how this (or anything) works on Windows.

Once you have fuse installed:

1. Create a [Monzo developer account](https://developers.getmondo.co.uk/).
2. Create a [new oauth client](https://developers.getmondo.co.uk/apps/new) with `http://localhost:1234/` listed as a "Redirect URL". Note the client id and secret (you need them later).
3. Install monzo-fs: `pip install monzo-fs`
4. Run monzo-fs: `monzo-fs /tmp/monzo --client_id=<yours> --client_secret=<yours>`.
5. Run through the oauth dance (click the link in terminal, put in your email, click the link in your email, go back to terminal).
6. 🎉 You're good to go, monzo-fs is mounted on `/tmp/monzo`! 🎉

## Config

monzo-fs stores state between starts in `~/.monzofs`. This file contains a valid oauth token so you don't have to constantly re-authorize everytime you restart the program.

## Examples

Some random examples to get you started/excited. Basically it's possible to explore your transaction history in a pretty meaningful way by looking at it as a file system. monzo-fs is designed to be relatively efficient so you don't have to be (e.g. we cache slow requests like listing transactions) but not overly agressive so data is relatively fresh (e.g. most caches live a few minutes).

### Retrieve your balance

```
$ ls -l /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/balance/
total 24
-r--r--r--  0 root  wheel  6  1 Jan  1970 balance
-r--r--r--  0 root  wheel  4  1 Jan  1970 currency
-r--r--r--  0 root  wheel  7  1 Jan  1970 spend_today

$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/balance/balance
41.44

$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/balance/spend_today
-55.69
```

### Print the notes from a specific transaction

```
$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2015/08/tx_00008zIcpb1TB4yeIFXMzx/notes
Salmon sandwich 🍞
```

### Print the number of transactions per day in a given month

```
$ cat /tmp/monzo/acc_00009Aq4VDixoGFnIxcBmr/transactions/2016/08/*/created | cut -d T -f 1 | cut -d - -f 3 | sort | uniq -c
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
for account in "$(ls -1 /tmp/monzo/)"; do
    # For each account...
    
    # 1) Create and truncate a file to hold date/balance pairs.
    touch "/tmp/monzo-balance-${account}"
    > "/tmp/monzo-balance-${account}"

    # 2) Loop through all transactions in 2016/08 and get the created time and balance.
    for txn in "/tmp/monzo/${account}/transactions/2016/08/"*; do
        # Print out "date time balance" records.
        created="$(cat "${txn}/created" | cut -d . -f 1)"
        balance="$(cat "${txn}/account_balance")"
        echo "${created} ${balance}" >> /tmp/monzo-balance-${account}
    done 

    # 3) Plot as a graph using gnuplot.
    gnuplot << __EOF
    set terminal png
    set output '/tmp/monzo-balance-${account}.png'
    set xdata time
    set format x "%m/%d"
    set timefmt "%Y-%m-%dT%H:%M:%S"
    plot "/tmp/monzo-balance-${account}" using 1:2 with linespoints
__EOF

    # 4) Profit?
    rm -f "/tmp/monzo-balance-${account}"
    open "/tmp/monzo-balance-${account}.png"
done
```

**Example result:**

![img](http://i.imgur.com/stASKCZ.png)

## FAQ

### Can this spend my monzough?

Not at the moment (the Monzo API is read only). If [Monzo change this](https://trello.com/c/BwKL2zRy/31-initiate-payments-via-api) and the default oauth scope provides access to initiate payments then `monzo-fs` (or tokens granted by it) could theoretically do this.

### Is this safe to use?

Maybe, hopefully, probably not. I use it, you should make up your own mind. It's alpha.

### What permissions are files/folders given?

Files/folders have root:root as the owner (`{uid,gid} = 0`) and are world readable/listable.

### How do I unmount?

Easiest option is to `^C` the `monzo-fs` process. If you can't find it `pkill -f monzo-fs` might do it. Finally you can `umount -f /tmp/monzo` to kill the mount, but it's likely the `monzo-fs` process will hang around as a zombie.
