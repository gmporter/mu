#!/usr/bin/python

import os

from libmu import server, TerminalState, CommandListState

class ServerInfo(object):
    host_addr = None
    port_number = 13579

    quality_y = 30
    quality_str = "30_x"
    keyframe_distance = 16

    video_name = "sintel-4k-y4m_24"
    num_offset = 0
    num_parts = 1
    overprovision = 25

    lambda_function = "vpxenc"
    regions = ["us-east-1"]
    bucket = "excamera-us-east-1"
    out_file = None
    profiling = None

    cacert = None
    srvcrt = None
    srvkey = None

    num_list = None

class FinalState(TerminalState):
    extra = "(finished)"

class DumpSSIMState(CommandListState):
    extra = "(dumping ssim)"
    pipelined = False
    nextState = FinalState
    commandlist = [ ("OK:RETRIEVE(", "run:/usr/bin/perl ./y4m_chop_inplace.pl \"##TMPDIR##/orig.y4m\" \"##TMPDIR##/orig_\" 12 yesplease")
                  , ("OK:RETVAL(0)", "run:rm \"##TMPDIR##/orig_00000{4}.y4m\"")
                  , ("OK:RETVAL(0)", "run:echo \"##TMPDIR##/xc.ivf\" | ./xc-decode-bundle {2} > \"##TMPDIR##/out.y4m\"")
                  , ("OK:RETVAL(0)", "run:/usr/bin/perl ./y4m_chop_inplace.pl \"##TMPDIR##/out.y4m\" \"##TMPDIR##/out_\" 12 yesplease")
                  , ("OK:RETVAL(0)", "run:rm \"##TMPDIR##/out_00000{4}.y4m\"")
                  , ("OK:RETVAL(0)", "run:./xc-framesize \"##TMPDIR##/xc.ivf\" > \"##TMPDIR##/out.txt\"")
                  , ("OK:RETVAL(0)", "run:./dump_ssim \"##TMPDIR##/out_00000{5}.y4m\" \"##TMPDIR##/orig_00000{5}.y4m\" >> \"##TMPDIR##/out.txt\"")
                  , ("OK:RETVAL(0)", "upload:{0}/out_ssim_{3}/{1}.txt\0##TMPDIR##/out.txt")
                  , ("OK:UPLOAD(", "quit:")
                  ]

    def __init__(self, prevState, aNum=0):
        super(DumpSSIMState, self).__init__(prevState, aNum)
        vName = ServerInfo.video_name
        pStr = "%08d" % (self.actorNum + 2 * ServerInfo.num_offset)

        if (self.actorNum // 2) % ServerInfo.keyframe_distance == 0:
            stStr = ""
        else:
            stStr = "\"##TMPDIR##/final.state\""
        
        split_num = self.actorNum % 2
        split_inv = 1 - split_num

        qStr = ServerInfo.quality_str
        self.commands = [ s.format(vName, pStr, stStr, qStr, split_inv, split_num) if s is not None else None for s in self.commands ]

class DumpSSIMRetrieveState(CommandListState):
    extra = "(retrieving data)"
    # keep this state separate from the next one so that we can parallelize downloading with pipelined commands
    pipelined = True
    nextState = DumpSSIMState
    commandlist = [ ("OK:HELLO", "retrieve:{0}/{1}.y4m\0##TMPDIR##/orig.y4m")
                  , "retrieve:{0}/out_{3}/{1}.ivf\0##TMPDIR##/xc.ivf"
                  , "retrieve:{0}/final_state_{3}/{2}.state\0##TMPDIR##/final.state"
                  ]

    def __init__(self, prevState, aNum):
        if (aNum // 2) % ServerInfo.keyframe_distance == 0:
            self.commandlist = [ self.commandlist[i] for i in (0, 1) ]

        super(DumpSSIMRetrieveState, self).__init__(prevState, aNum)

        vName = ServerInfo.video_name
        pNum = (self.actorNum // 2) + ServerInfo.num_offset
        pStr = "%08d" % pNum
        prStr = "%08d" % (pNum - 1)

        qStr = ServerInfo.quality_str
        self.commands = [ s.format(vName, pStr, prStr, qStr) if s is not None else None for s in self.commands ]

def run():
    server.server_main_loop([], DumpSSIMRetrieveState, ServerInfo)

def main():
    server.options(ServerInfo)
    ServerInfo.num_parts *= 2

    # launch the lambdas
    event = { "mode": 1
            , "port": ServerInfo.port_number
            , "addr": ServerInfo.host_addr
            , "nonblock": 1
            , "bg_silent": 1
            , "cacert": ServerInfo.cacert
            , "srvcrt": ServerInfo.srvcrt
            , "srvkey": ServerInfo.srvkey
            , "bucket": ServerInfo.bucket
            }
    server.server_launch(ServerInfo, event, os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_ACCESS_KEY'])

    # run the server
    run()

if __name__ == "__main__":
    main()
