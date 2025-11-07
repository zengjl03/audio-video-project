from funasr import AutoModel

# model = AutoModel(model="fsmn-vad", model_revision="v2.0.4")

wav_file = f"audio/f4e087102a12aab1a49d1759e3429b31.wav"

model = AutoModel(model="fa-zh", model_revision="v2.0.4")

text_file = f"你看。哈哈哈。啊。好。芊芊，爸爸走。芊芊，芊芊。芊芊，芊。哈哈哈。你再回去看看，人家妹姐都。芊芊，芊芊。芊芊，芊。啊。哈哈。哈哈哈。哈哈哈。哈哈。哈哈。哈哈哈。哈哈。哈哈哈 。哈哈。顶遍，门。抖音。"
res = model.generate(input=(wav_file, text_file), data_type=("sound", "text"))
print(res)