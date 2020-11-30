#!/usr/bin/env python3
# Copyright (c) 2018-2019 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

from decimal import Decimal

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import (
    assert_equal,
    assert_raises_rpc_error,
)
from test_framework.blocktools import (
    TIME_GENESIS_BLOCK,
)


class CreateTxWalletTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1
        self.wallet_names = ["test_wallet"]

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        self.log.info('Create some old blocks')
        self.nodes[0].setmocktime(TIME_GENESIS_BLOCK)
        self.nodes[0].generate(200)
        self.nodes[0].setmocktime(0)

        self.test_anti_fee_sniping()
        self.test_tx_size_too_large()
        self.test_setfeerate()

    def test_anti_fee_sniping(self):
        self.log.info('Check that we have some (old) blocks and that anti-fee-sniping is disabled')
        assert_equal(self.nodes[0].getblockchaininfo()['blocks'], 200)
        txid = self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(), 1)
        tx = self.nodes[0].decoderawtransaction(self.nodes[0].gettransaction(txid)['hex'])
        assert_equal(tx['locktime'], 0)

        self.log.info('Check that anti-fee-sniping is enabled when we mine a recent block')
        self.nodes[0].generate(1)
        txid = self.nodes[0].sendtoaddress(self.nodes[0].getnewaddress(), 1)
        tx = self.nodes[0].decoderawtransaction(self.nodes[0].gettransaction(txid)['hex'])
        assert 0 < tx['locktime'] <= 201

    def test_tx_size_too_large(self):
        # More than 10kB of outputs, so that we hit -maxtxfee with a high feerate
        outputs = {self.nodes[0].getnewaddress(address_type='bech32'): 0.000025 for _ in range(400)}
        raw_tx = self.nodes[0].createrawtransaction(inputs=[], outputs=outputs)

        for fee_setting in ['-minrelaytxfee=0.01', '-mintxfee=0.01', '-paytxfee=0.01']:
            self.log.info('Check maxtxfee in combination with {}'.format(fee_setting))
            self.restart_node(0, extra_args=[fee_setting])
            assert_raises_rpc_error(
                -6,
                "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)",
                lambda: self.nodes[0].sendmany(dummy="", amounts=outputs),
            )
            assert_raises_rpc_error(
                -4,
                "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)",
                lambda: self.nodes[0].fundrawtransaction(hexstring=raw_tx),
            )

        self.log.info('Check maxtxfee in combination with settxfee')
        self.restart_node(0)
        self.nodes[0].settxfee(0.01)
        assert_raises_rpc_error(
            -6,
            "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)",
            lambda: self.nodes[0].sendmany(dummy="", amounts=outputs),
        )
        assert_raises_rpc_error(
            -4,
            "Fee exceeds maximum configured by user (e.g. -maxtxfee, maxfeerate)",
            lambda: self.nodes[0].fundrawtransaction(hexstring=raw_tx),
        )
        self.nodes[0].settxfee(0)

    def test_setfeerate(self):
        self.log.info("Test setfeerate")
        self.restart_node(0, extra_args=["-mintxfee=0.00003141"])  # 3.141 sat/vB
        node = self.nodes[0]

        def test_response(*, requested=0, expected=0, error=None, msg):
            assert_equal(node.setfeerate(requested), {"wallet_name": "test_wallet", "fee_rate": expected, ("error" if error else "result"): msg})

        # Test setfeerate with too high/low values returns expected errors
        test_response(requested=Decimal("10000.001"), error=True, msg="The requested fee rate of 10000.001 sat/vB cannot be greater than the wallet max fee rate of 10000.000 sat/vB. The current setting of 0.000 sat/vB for this wallet remains unchanged.")

        test_response(requested=Decimal("0.999"), error=True, msg="The requested fee rate of 0.999 sat/vB cannot be less than the minimum relay fee rate of 1.000 sat/vB. The current setting of 0.000 sat/vB for this wallet remains unchanged.")

        test_response(requested=Decimal("3.140"), error=True, msg="The requested fee rate of 3.140 sat/vB cannot be less than the wallet min fee rate of 3.141 sat/vB. The current setting of 0.000 sat/vB for this wallet remains unchanged.")

        # Test setfeerate with valid values returns expected results
        assert_equal(node.getwalletinfo()["paytxfee"], Decimal("0.000"))

        test_response(requested=4, expected=4, msg="Fee rate for transactions with this wallet successfully set to 4.000 sat/vB")
        assert_equal(node.getwalletinfo()["paytxfee"], Decimal("0.00004000"))

        test_response(requested=3.141, expected=Decimal("3.141"), msg="Fee rate for transactions with this wallet successfully set to 3.141 sat/vB")
        assert_equal(node.getwalletinfo()["paytxfee"], Decimal("0.00003141"))

        test_response(msg="Fee rate for transactions with this wallet successfully unset. By default, automatic fee selection will be used.")
        assert_equal(node.getwalletinfo()["paytxfee"], 0)


if __name__ == '__main__':
    CreateTxWalletTest().main()
