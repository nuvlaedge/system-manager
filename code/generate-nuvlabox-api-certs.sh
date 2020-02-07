#!/bin/sh


header_message="Wrapper for generating self-signed certificates"

usage="--certs-folder </path> --server-key <server-key.pem> --server-cert <server-cert.pem>
            --client-key <client-key.pem> --client-cert <client-cert.pem>"


while [[ $# -gt 0 ]]
do
  key="$1"

  case $key in
      --certs-folder)
      CERTS_FOLDER="$2"
      shift # past argument
      shift # past value
      ;;
      --server-key)
      SERVER_KEY_NAME="$2"
      shift
      shift
      ;;
      --server-cert)
      SERVER_CERT_NAME="$2"
      shift
      shift
      ;;
      --client-key)
      CLIENT_KEY_NAME="$2"
      shift
      shift
      ;;
      --client-cert)
      CLIENT_CERT_NAME="$2"
      shift
      shift
      ;;
      *)
      echo -e "ERR: Unknown ${1} ${2}. Usage: \n\t ${usage}"
      exit 128
      ;;
  esac
done

HOST=${HOST:-`hostname`}
SUBJECT_ALT_NAMES="DNS:${HOST}"

PASSPHRASE=$(openssl rand -base64 32)

CA_KEY="${CERTS_FOLDER}/ca-key.pem"
CA="${CERTS_FOLDER}/ca.pem"
SERVER_KEY="${CERTS_FOLDER}/${SERVER_KEY_NAME}"
SERVER_CERT="${CERTS_FOLDER}/${SERVER_CERT_NAME}"
SERVER_CSR="${CERTS_FOLDER}/server.csr"
EXTFILE="${CERTS_FOLDER}/extfile.cnf"
CLIENT_KEY="${CERTS_FOLDER}/${CLIENT_KEY_NAME}"
CLIENT_CERT="${CERTS_FOLDER}/${CLIENT_CERT_NAME}"
CLIENT_CSR="${CERTS_FOLDER}/client.csr"

openssl genrsa -aes256 -out "${CA_KEY}" -passout pass:$PASSPHRASE 4096
openssl req -new -x509 -days 365 -key "${CA_KEY}" -sha256 -out "${CA}" \
        -passin pass:${PASSPHRASE} -subj "/C=CH/L=Geneva/O=SixSq/CN=$HOST"

# Generate server credentials
openssl genrsa -out "${SERVER_KEY}" 4096
openssl req -subj "/CN=$HOST" -sha256 -new -key "${SERVER_KEY}" -out "${SERVER_CSR}"

echo subjectAltName = ${SUBJECT_ALT_NAMES} > "${EXTFILE}"
openssl x509 -req -days 365 -sha256 -in "${SERVER_CSR}" -CA "${CA}" -CAkey "${CA_KEY}" \
        -CAcreateserial -out "${SERVER_CERT}" -extfile "${EXTFILE}" -passin pass:${PASSPHRASE}

# Generate client credentials
openssl genrsa -out "${CLIENT_KEY}" 4096
openssl req -subj '/CN=client' -new -key "${CLIENT_KEY}" -out "${CLIENT_CSR}"

echo extendedKeyUsage = clientAuth > "${EXTFILE}"
openssl x509 -req -days 365 -sha256 -in "${CLIENT_CSR}" -CA "${CA}" -CAkey "${CA_KEY}" \
        -CAcreateserial -out "${CLIENT_CERT}" -extfile "${EXTFILE}" -passin pass:${PASSPHRASE}

# cleanup
rm -v "${CLIENT_CSR}" "${SERVER_CSR}"
chmod -v 0400 "${CA_KEY}" "${CLIENT_KEY}" "${SERVER_KEY}"
chmod -v 0444 "${CA}" "${SERVER_CERT}" "${CLIENT_CERT}"

