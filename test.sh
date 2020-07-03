#!/bin/bash

echo "Linting code..."
pylint *.py tests/*.py psclient/*.py --disable=R,fixme || pylint-exit -wfail -efail -cfail $?
LINT_SUCCESS=$?
echo "Running tests..."
pytest tests/
TEST_SUCCESS=$?

if [ $LINT_SUCCESS == 0 ] && [ $TEST_SUCCESS == 0 ]; then
    echo "Success!"
    exit 0
elif [ $LINT_SUCCESS == 0 ]; then
    echo "Linting passed, but tests failed."
    exit 1
elif [ $TEST_SUCCESS == 0 ]; then
    echo "Tests passed, but linting failed."
    exit 1
else
    echo "Both tests and linting failed :c"
    exit 2
fi
