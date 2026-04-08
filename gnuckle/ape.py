"""Ape wisdom dispensary. Loading phrases, status messages, and primate philosophy."""

import random
import time
import sys

# ── APE LOADING PHRASES ──────────────────────────────────────────────────────
# shown during server startup, cooldowns, and wait states

LOADING_PHRASES = [
    "ape eat banana...",
    "consulting Harambe...",
    "all hail Caesar...",
    "monke think...",
    "ape together strong...",
    "return to monke...",
    "peeling banana for GPU...",
    "ape no fight ape. ape fight benchmark...",
    "checking if banana is ripe...",
    "grooming the KV cache...",
    "ooh ooh aah aah (loading)...",
    "ape see number go up. ape happy...",
    "shaking the banana tree...",
    "Harambe guides our tensors...",
    "knuckle-walking through VRAM...",
    "scratching head. then scratching GPU...",
    "this one for Harambe...",
    "ape brain wrinkle forming...",
    "throwing benchmark at wall. see what stick...",
    "monke no need sleep. monke need tok/s...",
    "banana per token ratio: optimal...",
    "where banana? banana in cache...",
    "ape read CUDA docs. ape confused. ape try anyway...",
    "Planet of the Apes was a documentary...",
    "evolving... please wait...",
    "stonks go up. tok/s go up. same energy...",
    "diamond hands on this benchmark...",
    "not financial advice. is banana advice...",
    "Harambe died for our benchmarks...",
    "reject modernity. embrace monke...",
    "ape strong alone. ape stronger with turbo3...",
    "smooth brain loading smooth cache...",
    "1 banana = 1 banana. 1 token = 1 token...",
    "GNU is Not Unix. Gnuckle is Not Subtle...",
    "free as in freedom. free as in banana...",
    "chmod 777 banana.txt...",
    "sudo make me a benchmark...",
    "ape fork repo. ape fork banana...",
    "dis is de way...",
    "do u kno de way? de way is benchmark...",
    "ape show u de way to tok/s...",
    "de way of de cache is de way of de ape...",
    "follow de way. trust de numbers...",
    "u do not kno de way. but gnuckle kno...",
    "spit on false benchmarks. dis is de way...",
    "de queen commands: run de benchmark...",
    "we must find de way. de way is turbo3...",
]

STARTUP_PHRASES = [
    "ape wake up. ape choose violence (benchmarking).",
    "good morning. time to drag knuckle across GPU.",
    "Harambe watches over this benchmark session.",
    "ape boot sequence initiated. banana fuel: full.",
    "monke has entered the chat.",
    "from the trees to the tensors. let's go.",
]

COOLDOWN_PHRASES = [
    "ape rest between rounds. eat banana...",
    "cooling GPU. ape blow on it...",
    "brief return to monke before next run...",
    "Harambe intermission. stretch your knuckles...",
    "ape hydrate. GPU hydrate. everyone hydrate...",
    "scratching armpit contemplatively...",
]

COMPLETION_PHRASES = [
    "ape did it. benchmark complete. banana earned.",
    "Harambe smiles from above. the numbers are in.",
    "monke finished. results in the banana pile.",
    "all cache types benchmarked. ape rest now.",
    "from f16 to turbo3. what a time to be ape.",
    "the jungle has spoken. check your results.",
]

ERROR_PHRASES = [
    "ape confused. something broke. ape try again...",
    "banana peel detected. ape slipped...",
    "Harambe would not have wanted this error...",
    "monke see red. not the good kind of red...",
    "ape scratch head. GPU scratch head. nobody know...",
]

SERVER_WAIT_PHRASES = [
    "ape poke server with stick...",
    "is server alive? ape listen closely...",
    "waiting for server like ape wait for banana truck...",
    "ape stare at port. port stare back...",
    "server loading. ape patient. ape zen...",
]

SERVER_UP_PHRASES = [
    "server respond! ape celebrate!",
    "connection established. banana pipeline active.",
    "the monke network is online.",
    "server up. knuckles: cracked. benchmark: imminent.",
]

SERVER_KILL_PHRASES = [
    "ape gently put server to sleep...",
    "server go night night...",
    "pulling the banana plug...",
    "taskkill, but with love...",
]


def ape_phrase(category="loading"):
    """Get a random ape phrase from the specified category."""
    pools = {
        "loading":     LOADING_PHRASES,
        "startup":     STARTUP_PHRASES,
        "cooldown":    COOLDOWN_PHRASES,
        "completion":  COMPLETION_PHRASES,
        "error":       ERROR_PHRASES,
        "server_wait": SERVER_WAIT_PHRASES,
        "server_up":   SERVER_UP_PHRASES,
        "server_kill": SERVER_KILL_PHRASES,
    }
    return random.choice(pools.get(category, LOADING_PHRASES))


def ape_print(category="loading", prefix="  >> "):
    """Print a random ape phrase."""
    print(f"{prefix}{ape_phrase(category)}")


def ape_wait(seconds, category="loading"):
    """Wait with ape commentary. Shows a phrase partway through."""
    if seconds <= 2:
        ape_print(category)
        time.sleep(seconds)
        return
    half = seconds / 2
    ape_print(category)
    time.sleep(half)
    ape_print("loading")
    time.sleep(seconds - half)
