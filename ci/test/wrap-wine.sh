#!/usr/bin/env bash
#
# Copyright (c) 2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.

export LC_ALL=C.UTF-8

for b_name in {"${BASE_OUTDIR}/bin"/*,src/secp256k1/*tests,src/univalue/{no_nul,test_json,unitester,object}}.exe; do
    # shellcheck disable=SC2044
    for b in $(find "${BASE_ROOT_DIR}" -executable -type f -name "$(basename $b_name)"); do
      filetype="$(file -b "$b")"
      if grep -q "Windows" <<<"${filetype}"; then
        echo "Wrap $b ..."
        mv "$b" "${b}_orig"
        echo '#!/usr/bin/env bash' > "$b"
        if grep -q "\b64\b" <<<"${filetype}"; then
        echo "wine64 \"${b}_orig\" \"\$@\"" >> "$b"
        else
          echo "wine \"${b}_orig\" \"\$@\"" >> "$b"
        fi
        chmod +x "$b"
      fi
    done
done
