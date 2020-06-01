// Copyright (c) 2020 The Bitcoin Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#ifndef BITCOIN_WALLET_DUMP_H
#define BITCOIN_WALLET_DUMP_H

class CWallet;

struct bilingual_str;

bool DumpWallet(std::shared_ptr<CWallet> wallet, bilingual_str& error);

#endif // BITCOIN_WALLET_DUMP_H
