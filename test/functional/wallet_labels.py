#!/usr/bin/env python3
# Copyright (c) 2016-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test label RPCs.

RPCs tested are:
    - getaddressesbylabel
    - listaddressgroupings
    - setlabel
"""
from collections import defaultdict

from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_equal, assert_raises_rpc_error
from test_framework.wallet_util import test_address


class WalletLabelsTest(BitcoinTestFramework):
    def set_test_params(self):
        self.setup_clean_chain = True
        self.num_nodes = 1

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def test_sort_multisig(self, node):
        node.importprivkey("cSJUMwramrFYHKPfY77FH94bv4Q5rwUCyfD6zX3kLro4ZcWsXFEM")
        node.importprivkey("cSpQbSsdKRmxaSWJ3TckCFTrksXNPbh8tfeZESGNQekkVxMbQ77H")
        node.importprivkey("cRNbfcJgnvk2QJEVbMsxzoprotm1cy3kVA2HoyjSs3ss5NY5mQqr")

        addresses = [
            "muRmfCwue81ZT9oc3NaepefPscUHtP5kyC",
            "n12RzKwqWPPA4cWGzkiebiM7Gu6NXUnDW8",
            "n2yWMtx8jVbo8wv9BK2eN1LdbaakgKL3Mt",
        ]

        sorted_default = node.addmultisigaddress(2, addresses, None, 'legacy')
        sorted_false = node.addmultisigaddress(2, addresses, {"sort": False}, 'legacy')
        sorted_true = node.addmultisigaddress(2, addresses, {"sort": True}, 'legacy')

        assert_equal(sorted_default, sorted_false)
        assert_equal("2N6dne8yzh13wsRJxCcMgCYNeN9fxKWNHt8", sorted_default['address'])
        assert_equal("2MsJ2YhGewgDPGEQk4vahGs4wRikJXpRRtU", sorted_true['address'])

        sorted_default = node.addmultisigaddress(2, addresses, {'address_type': 'legacy'})
        sorted_false = node.addmultisigaddress(2, addresses, {'address_type': 'legacy', "sort": False})
        sorted_true = node.addmultisigaddress(2, addresses, {'address_type': 'legacy', "sort": True})

        assert_equal(sorted_default, sorted_false)
        assert_equal("2N6dne8yzh13wsRJxCcMgCYNeN9fxKWNHt8", sorted_default['address'])
        assert_equal("2MsJ2YhGewgDPGEQk4vahGs4wRikJXpRRtU", sorted_true['address'])

        assert_raises_rpc_error(-1, "address_type provided in both options and 4th parameter", node.addmultisigaddress, 2, addresses, {"address_type": 'legacy'}, 'bech32')

    def test_sort_multisig_with_uncompressed_hash160(self, node):
        node.importpubkey("02632b12f4ac5b1d1b72b2a3b508c19172de44f6f46bcee50ba33f3f9291e47ed0")
        node.importpubkey("04dd4fe618a8ad14732f8172fe7c9c5e76dd18c2cc501ef7f86e0f4e285ca8b8b32d93df2f4323ebb02640fa6b975b2e63ab3c9d6979bc291193841332442cc6ad")
        address = "2MxvEpFdXeEDbnz8MbRwS23kDZC8tzQ9NjK"

        addresses = [
            "msDoRfEfZQFaQNfAEWyqf69H99yntZoBbG",
            "myrfasv56W7579LpepuRy7KFhVhaWsJYS8",
        ]
        default = self.nodes[0].addmultisigaddress(2, addresses, {'address_type': 'legacy'})
        assert_equal(address, default['address'])

        unsorted = self.nodes[0].addmultisigaddress(2, addresses, {'address_type': 'legacy', "sort": False})
        assert_equal(address, unsorted['address'])

        assert_raises_rpc_error(-1, "Compressed key required for BIP67: myrfasv56W7579LpepuRy7KFhVhaWsJYS8", node.addmultisigaddress, 2, addresses, {"sort": True})

    def run_test(self):
        # Check that there's no UTXO on the node
        node = self.nodes[0]
        assert_equal(len(node.listunspent()), 0)

        # Note each time we call generate, all generated coins go into
        # the same address, so we call twice to get two addresses w/50 each
        node.generatetoaddress(nblocks=1, address=node.getnewaddress(label='coinbase'))
        node.generatetoaddress(nblocks=101, address=node.getnewaddress(label='coinbase'))
        assert_equal(node.getbalance(), 100)

        # there should be 2 address groups
        # each with 1 address with a balance of 50 Bitcoins
        address_groups = node.listaddressgroupings()
        assert_equal(len(address_groups), 2)
        # the addresses aren't linked now, but will be after we send to the
        # common address
        linked_addresses = set()
        for address_group in address_groups:
            assert_equal(len(address_group), 1)
            assert_equal(len(address_group[0]), 3)
            assert_equal(address_group[0][1], 50)
            assert_equal(address_group[0][2], 'coinbase')
            linked_addresses.add(address_group[0][0])

        # send 50 from each address to a third address not in this wallet
        common_address = "msf4WtN1YQKXvNtvdFYt9JBnUD2FB41kjr"
        node.sendmany(
            amounts={common_address: 100},
            subtractfeefrom=[common_address],
            minconf=1,
        )
        # there should be 1 address group, with the previously
        # unlinked addresses now linked (they both have 0 balance)
        address_groups = node.listaddressgroupings()
        assert_equal(len(address_groups), 1)
        assert_equal(len(address_groups[0]), 2)
        assert_equal(set([a[0] for a in address_groups[0]]), linked_addresses)
        assert_equal([a[1] for a in address_groups[0]], [0, 0])

        node.generate(1)

        # we want to reset so that the "" label has what's expected.
        # otherwise we're off by exactly the fee amount as that's mined
        # and matures in the next 100 blocks
        amount_to_send = 1.0

        # Create labels and make sure subsequent label API calls
        # recognize the label/address associations.
        labels = [Label(name) for name in ("a", "b", "c", "d", "e")]
        for label in labels:
            address = node.getnewaddress(label.name)
            label.add_receive_address(address)
            label.verify(node)

        # Check all labels are returned by listlabels.
        assert_equal(node.listlabels(), sorted(['coinbase'] + [label.name for label in labels]))

        # Send a transaction to each label.
        for label in labels:
            node.sendtoaddress(label.addresses[0], amount_to_send)
            label.verify(node)

        # Check the amounts received.
        node.generate(1)
        for label in labels:
            assert_equal(
                node.getreceivedbyaddress(label.addresses[0]), amount_to_send)
            assert_equal(node.getreceivedbylabel(label.name), amount_to_send)

        for i, label in enumerate(labels):
            to_label = labels[(i + 1) % len(labels)]
            node.sendtoaddress(to_label.addresses[0], amount_to_send)
        node.generate(1)
        for label in labels:
            address = node.getnewaddress(label.name)
            label.add_receive_address(address)
            label.verify(node)
            assert_equal(node.getreceivedbylabel(label.name), 2)
            label.verify(node)
        node.generate(101)

        # Check that setlabel can assign a label to a new unused address.
        for label in labels:
            address = node.getnewaddress()
            node.setlabel(address, label.name)
            label.add_address(address)
            label.verify(node)
            assert_raises_rpc_error(-11, "No addresses with label", node.getaddressesbylabel, "")

        # Check that addmultisigaddress can assign labels.
        if not self.options.descriptors:
            for label in labels:
                addresses = []
                for _ in range(10):
                    addresses.append(node.getnewaddress())
                multisig_address = node.addmultisigaddress(5, addresses, label.name)['address']
                label.add_address(multisig_address)
                label.purpose[multisig_address] = "send"
                label.verify(node)
            node.generate(101)

        # Check that setlabel can change the label of an address from a
        # different label.
        change_label(node, labels[0].addresses[0], labels[0], labels[1])

        # Check that setlabel can set the label of an address already
        # in the label. This is a no-op.
        change_label(node, labels[2].addresses[0], labels[2], labels[2])

        if not self.options.descriptors:
            self.test_sort_multisig(node)
            self.test_sort_multisig_with_uncompressed_hash160(node)

        self.log.info('Check watchonly labels')
        node.createwallet(wallet_name='watch_only', disable_private_keys=True)
        wallet_watch_only = node.get_wallet_rpc('watch_only')
        BECH32_VALID = {
            '✔️_VER15_PROG40': 'bcrt10qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqn2cjv3',
            '✔️_VER16_PROG03': 'bcrt1sqqqqqjq8pdp',
            '✔️_VER16_PROB02': 'bcrt1sqqqqqjq8pv',
        }
        BECH32_INVALID = {
            '❌_VER15_PROG41': 'bcrt10qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqzc7xyq',
            '❌_VER16_PROB01': 'bcrt1sqqpl9r5c',
        }
        for l in BECH32_VALID:
            ad = BECH32_VALID[l]
            wallet_watch_only.importaddress(label=l, rescan=False, address=ad)
            node.generatetoaddress(1, ad)
            assert_equal(wallet_watch_only.getaddressesbylabel(label=l), {ad: {'purpose': 'receive'}})
            assert_equal(wallet_watch_only.getreceivedbylabel(label=l), 0)
        for l in BECH32_INVALID:
            ad = BECH32_INVALID[l]
            assert_raises_rpc_error(
                -5,
                "Address is not valid" if self.options.descriptors else "Invalid Bitcoin address or script",
                lambda: wallet_watch_only.importaddress(label=l, rescan=False, address=ad),
            )


class Label:
    def __init__(self, name):
        # Label name
        self.name = name
        # Current receiving address associated with this label.
        self.receive_address = None
        # List of all addresses assigned with this label
        self.addresses = []
        # Map of address to address purpose
        self.purpose = defaultdict(lambda: "receive")

    def add_address(self, address):
        assert_equal(address not in self.addresses, True)
        self.addresses.append(address)

    def add_receive_address(self, address):
        self.add_address(address)

    def verify(self, node):
        if self.receive_address is not None:
            assert self.receive_address in self.addresses
        for address in self.addresses:
            test_address(node, address, labels=[self.name])
        assert self.name in node.listlabels()
        assert_equal(
            node.getaddressesbylabel(self.name),
            {address: {"purpose": self.purpose[address]} for address in self.addresses})

def change_label(node, address, old_label, new_label):
    assert_equal(address in old_label.addresses, True)
    node.setlabel(address, new_label.name)

    old_label.addresses.remove(address)
    new_label.add_address(address)

    old_label.verify(node)
    new_label.verify(node)

if __name__ == '__main__':
    WalletLabelsTest().main()
