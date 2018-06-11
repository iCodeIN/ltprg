#!/bin/bash

#export CUDA_LAUNCH_BLOCKING=1
export CUDA_VISIBLE_DEVICES=1
export GPU=1
export SEED=${CUDA_VISIBLE_DEVICES}
export EVAL_TEST=0
export CLEAN_LENGTH=12
export ROOT_DIR=[PATH_TO_LTPRG_DIRECTORY]
export SCRIPT=${ROOT_DIR}/src/test/py/ltprg/game/colorGrids/model/learn_S.py
export ENV_FILE=${ROOT_DIR}/env_local.json
export DATA_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/data/cgmerged_cpos_unclean.json
export MODEL_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/model/s0/attn_cgmerged.json
export LEARN_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/learn/s/cgmerged_src_grid3_data.json
export TRAIN_EVALS_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/eval/s/cgmerged_train_src_grid3.json
export DEV_EVALS_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/eval/s/cgmerged_dev_src_grid3.json
export TEST_EVALS_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/eval/s/cgmerged_test_src_grid3.json
export OUTPUT_DIR=[PATH_TO_OUTPUT_DIRECTORY]

cd ${ROOT_DIR}

sizes=( 250 500 1000 2500 5000 )
for sz in "${sizes[@]}"
do
    export TRAIN_DATA=train_src_grid3_cleanutts
    export TRAIN_SIZE=${sz}
    export JOB_ID=s0_onlygrid_${TRAIN_SIZE}
    export LEARN_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/learn/s/cgmerged_src_grid3_data.json
    python ${SCRIPT} ${JOB_ID} ${ENV_FILE} ${DATA_CONFIG_FILE} ${MODEL_CONFIG_FILE} ${LEARN_CONFIG_FILE} ${TRAIN_EVALS_CONFIG_FILE} ${DEV_EVALS_CONFIG_FILE} ${TEST_EVALS_CONFIG_FILE} ${OUTPUT_DIR} --gpu ${GPU} --seed ${SEED} --eval_test ${EVAL_TEST} --clean_length ${CLEAN_LENGTH} --train_data ${TRAIN_DATA} --train_data_size ${TRAIN_SIZE}
done

export JOB_ID=s0_onlygrid_full
export LEARN_CONFIG_FILE=${ROOT_DIR}/config/game/colorGrids/learn/s/cgmerged_src_grid3.json
python ${SCRIPT} ${JOB_ID} ${ENV_FILE} ${DATA_CONFIG_FILE} ${MODEL_CONFIG_FILE} ${LEARN_CONFIG_FILE} ${TRAIN_EVALS_CONFIG_FILE} ${DEV_EVALS_CONFIG_FILE} ${TEST_EVALS_CONFIG_FILE} ${OUTPUT_DIR} --gpu ${GPU} --seed ${SEED} --eval_test ${EVAL_TEST} --clean_length ${CLEAN_LENGTH}




