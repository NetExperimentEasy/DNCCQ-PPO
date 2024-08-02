"""
                                  
        |-> root-eth0
        |
c1 --- sw1 --- ser1
        |
c2 --- sw2 --- ser2
        |
c3 --- sw3 --- ser3

"""

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink


def runMultiLink():
    "Create and run multiple link network"
    topo = multiTopo(n=2)
    net = Mininet(topo=topo, link=TCLink, waitConnected=True)
    net.start()
    CLI(net)
    net.stop()


class multiTopo(Topo):
    "Simple topology with multiple links"

    def build(self, n, **_kwargs):

        # while use root-eth0, 10.0.0.1 cant be used, so set a useless client
        self.addHost('c0')
        # sw0 = self.addSwitch( 'sw0' )
        # self.addLink( c0 ,sw0 )

        switchlist = []
        for i in range(n):
            si, ci = self.addHost(f'ser{i+1}'), self.addHost(f'c{i+1}')
            swi = self.addSwitch(f'sw{i+1}')
            self.addLink(ci, swi)
            self.addLink(swi, si)
            switchlist.append(swi)

        for item in switchlist[1:]:
            self.addLink(switchlist[0], item)


if __name__ == '__main__':
    setLogLevel('info')
    runMultiLink()
