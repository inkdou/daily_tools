#!/usr/bin/python
import os
import sys
from subprocess import PIPE, Popen
import StringIO
import ConfigParser
import re
import fcntl
import netifaces
from pyroute2 import IPRoute
from pyroute2 import iproute
from IPy import IP as IPS

def read_rttables(file_path):
    strinfo = re.compile('[\t|" "]+')
    with open(file_path) as f:
        config = StringIO.StringIO()
        config.write('[dummy_section]\n')
        config.write(strinfo.sub('=', f.read()))
        config.seek(0, os.SEEK_SET)

        cp = ConfigParser.SafeConfigParser()
        cp.readfp(config)
        conf = dict(cp.items('dummy_section'))
        dic = {}
        max = 100
        for key in conf:
            dic[conf[key]] = key
            if key > max and key < 253:
                max = key

        return dic,max

def run():
    #nics = {}
    #count = 100
    nics, count = read_rttables("/etc/iproute2/rt_tables")
    ipr = IPRoute()
    cmd = "echo 1 > /proc/sys/net/ipv4/conf/all/arp_ignore"
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
    p.wait()

    while True:
        for interface in netifaces.interfaces():
            if interface == "lo":
                continue
            try:
                ip = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['addr']
                mask = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]['netmask']
            except KeyError:
                ip = ""
                mask = ""
                continue

            if nics.has_key(interface):
                state = ipr.get_links(ipr.link_lookup(ifname=interface))[0].get_attr('IFLA_OPERSTATE')
                #rule operation
                table_id = int(nics[interface])
                ipret = ipr.get_rules(table=table_id)
                if ipret:
                    iprlist = {}
                    if ipret:
                        for i in ipret[0]['attrs']:
                            iprlist[i[0]] = i[1]
                        #current ip is NULL
                        if not ip or state == "DOWN":
                            print interface, " ", table_id, " ", state, " del ", ip, " ", " ", mask, "\n"
                            ipr.rule("del", table=table_id, priority=iprlist['FRA_PRIORITY'])
                        else:
                            if ip != iprlist['FRA_SRC']:
                                print interface, " neq del ", ip, " ", " ", mask, "\n"
                                ipr.rule("del", table=table_id, priority=iprlist['FRA_PRIORITY'])
                                ipr.rule("add", table=table_id, src=ip)
                else:
                    if ip:
                        #add rule
                        if state != "DOWN":
                            ipr.rule("add", table=table_id, src=ip)


                #route operation
                if state == "DOWN":
                    continue

                routelist = ipr.get_routes(table=table_id)
                if routelist:
                    pass
                else:
                    idx = ipr.link_lookup(ifname=interface)[0]
                    ipss = IPS(ip).make_net(mask)
                    ipr.route('add', dst=str(ipss),  oif=idx, prefsrc=ip, table=table_id)

            else:
                #only once
                count += 1
                cmd = "echo \"%d %s\" >> /etc/iproute2/rt_tables" % (count, interface)
                p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
                p.wait()
                #update table id
                nics[interface] = count

def checkonce():
    try:
        pidfile = open("/tmp/mintu.pid", "r")
        try:
            fcntl.flock(pidfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except:
            print "another process is running..."
            sys.exit(1)
    except IOError:
        pid = str(os.getpid())
        f = open('/tmp/mintu.pid', 'w')
        f.write(pid)
        f.close()


def main():
    checkonce()
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError, e:
        print >> sys.stderr,"fork failed:%d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

    os.chdir("/")
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError, e:
        print >> sys.stderr, "fork failed:%d (%s)" % (e.errno, e.strerror)
        sys.exit(1)
    run()

if __name__ == '__main__':
    main()
