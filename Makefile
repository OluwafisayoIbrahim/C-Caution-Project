# make test   : build and run the host-side firmware tests (needs a C++11 compiler)
# make check  : run the netlist checker on parts.csv / wiring.csv (needs Python 3)
# make netlist: regenerate parts.csv and wiring.csv, then check
# make all    : regenerate/check netlist + host tests + checker mutation tests

CXX ?= g++
BUILD := build

.PHONY: all test test-netlist check netlist clean

all: netlist test test-netlist

test:
	mkdir -p $(BUILD)
	$(CXX) -std=c++11 -Wall -Wextra -o $(BUILD)/test_sequencer tests/test_sequencer.cpp
	./$(BUILD)/test_sequencer

test-netlist:
	python3 tests/test_netlist.py

check:
	python3 tools/check_netlist.py .

netlist:
	python3 tools/generate_netlist.py
	python3 tools/check_netlist.py .

clean:
	rm -rf $(BUILD)
