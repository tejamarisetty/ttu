#!/usr/bin/python3

import socket
import click
import time
import random
import os
import re

from fuzzer.probabilistichttpfuzzer import prob_http_fuzzer
from loguru import logger
from xeger import Xeger

UUID_REGEX = "[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}"

@click.command()
@click.argument('template', type=click.File('rb'), required=False)
@click.argument('substitutions', type=click.File('rb'), required=False)
@click.option('--log-file', required=False, multiple=True)
@click.option('--port', default=80)
@click.option('--mode', type=click.Choice(['grammar', 'nmap']), default='grammar')
@click.option('--protocol', default='http')
def stub(template, substitutions, port, log_file, mode, protocol):
    """
    Run a stub that serves tracking responses.
    """
    # Create socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('0.0.0.0', port))
    s.listen()

    packet_logger = logger.bind(packet=True)
    packet_log_format = "{message}"

    TIMESTAMP = str(time.time()).split('.')[0]
    logger.add('full-{}.log'.format(TIMESTAMP))

    # Create debug log filter
    packet_filter = lambda record: "packet" in record["extra"]
    logger.add('packets-{}.log'.format(TIMESTAMP), filter=packet_filter, format=packet_log_format)
    for l in log_file:
        logger.add(l, filter=packet_filter, format=packet_log_format)
    logger.success("Socker listening on port {}", port)

    if template and substitutions:
        substitutions = [s.rstrip() for s in substitutions.readlines()]
        template = template.read()

        for substitution in substitutions:
            # TODO: take substitution chars as input
            current_payload = template.replace(b'$a', substitution)
            logger.info(template)
            logger.info(current_payload)
            logger.success("Current payload: {}", current_payload)
            packet_logger.debug(current_payload)
            logger.success("Accepting incoming connection")
            try:
                conn, addr = s.accept()
                logger.info("Recv data")
                data = conn.recv(1024)

                try:
                    logger.info(data.decode())
                except UnicodeDecodeError:
                    logger.info(data)

                conn.send(current_payload)
                conn.close()
            except Exception as e:
                logger.error("[-] Connection reset by peer")
                logger.error(e)

    else:
        while True:
            if mode == 'grammar':
                if protocol == 'http':
                    current_payload = prob_http_fuzzer()
                else:
                    raise Exception('Unsupported protocol')
            elif mode == 'nmap':
                # choose portocol
                protocol_file = 'protocols/{}'.format(protocol)
                # exception if no file
                if not os.path.isfile(protocol_file):
                    raise Exception('Unsupported protocol')
                regexes = open(protocol_file, 'r').readlines()
                chosen_regex = random.choice(regexes)

                search = re.search('(\(.*?\))', chosen_regex)

                if search:
                    candidate = search.group(1)
                    # add the possibility of injecting a UUID
                    chosen_regex = chosen_regex.replace(candidate, "(({})|({}))".format(candidate, UUID_REGEX))

                x = Xeger()
                current_payload = x.xeger(chosen_regex)

            # Check if click catches the error

            current_payload = bytes(current_payload, encoding='utf-8')

            logger.success("Current payload:\n{}", current_payload)
            packet_logger.debug(current_payload)
            logger.success("Accepting incoming connection")

            try:
                conn, addr = s.accept()
                logger.info("Recv data")
                data = conn.recv(65535)

                try:
                    logger.info(data.decode())
                except UnicodeDecodeError:
                    logger.info(data)

                conn.send(current_payload)
            except Exception as e:
                logger.error("[-] Connection reset by peer")
                logger.error(e)
            finally:
                conn.close()


if __name__ == "__main__":
    # §a§ §b§ §c§
    stub()
