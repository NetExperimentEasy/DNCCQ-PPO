from core.rlccenv import RlccMininet, PcapAt
from mininet.log import setLogLevel

setLogLevel('info')

XQUIC_PATH = '/home/seclee/xquic/xquic_forrlcc/build'

map_c_2_rlcc_flag = {
    'c1': "1001",
    'c2': "1002",
}

pcaplist = [
    PcapAt('c1', ['ser1'], ['8443'])
]

Exp = RlccMininet(map_c_2_rlcc_flag, XQUIC_PATH=XQUIC_PATH)

Exp.run_train("random")
# Exp.run_train("fix")

# Exp.cli()
