from core.rlccenv import RlccMininet, PcapAt
from mininet.log import setLogLevel

setLogLevel('info')

XQUIC_PATH = '/home/seclee/xquic/xquic_forrlcc/build'

map_c_2_rlcc_flag = {
    'c1': "1001",
    'c2': "1002",
    'c3': "1003",
    'c4': "1004",
    'c5': "1005",
    'c6': "1006",
    'c7': "1007",
    'c8': "1008",
    'c9': "1009",
    'c10': "1010",
}

pcaplist = [
    PcapAt('c1', ['ser1'], ['8443'])
]

Exp = RlccMininet(map_c_2_rlcc_flag, XQUIC_PATH=XQUIC_PATH)

Exp.cli()

# Exp.run_exp("fix", pcaplist)
