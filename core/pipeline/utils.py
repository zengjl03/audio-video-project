from typing import List, Dict,Any, Tuple
from loguru import logger
from tqdm import tqdm
import json
import os
import base64
from io import BytesIO
from pydub import AudioSegment
from openai import OpenAI
from dotenv import load_dotenv
from dataclasses import asdict
from core.utils import EventItem
load_dotenv()

class OutlineExtractorMixin:
    def _smart_chunk_segments(self, segments: List[Dict[str, Any]], segment_duration_minutes: int = 30, pause_threshold_ms: float = 1000.0) -> List[Dict[str, Any]]:
        """
        参照 autoclip 的时间智能分块逻辑，将转写片段切分为均匀时间块
        
        参数:
            segments: 转录片段列表，每个片段包含 start_time, end_time, text 等字段
            interval_minutes: 分块时间间隔（分钟），默认30分钟
            pause_threshold_ms: 停顿阈值（毫秒），用于在自然停顿处切分，默认1000毫秒
            
        返回:
            分块后的列表，每个块包含 chunk_index, text, start_time, end_time, segments
        """
        if not segments:
            return []

        # 为每个片段添加秒数字段，便于计算（不修改原始数据）
        segments_with_seconds = []
        for segment in segments:
            segment_with_seconds = segment.copy()
            segment_with_seconds['start_seconds'] = segment['start_time']
            segment_with_seconds['end_seconds'] = segment['end_time']
            segments_with_seconds.append(segment_with_seconds)

        segment_duration_seconds = segment_duration_minutes * 60
        result_chunks = []
        chunk_start_idx = 0
        chunk_idx = 0
        last_chunk_end_time = 0.0
        
        while chunk_start_idx < len(segments_with_seconds):
            target_chunk_end_time = last_chunk_end_time + segment_duration_seconds
            
            # 寻找接近目标时间的最佳切分点
            best_split_idx = -1
            
            # 查找从当前块开始后的 90% 到 110% 目标时间内的一个停顿
            search_start_idx = chunk_start_idx
            while (search_start_idx < len(segments_with_seconds) and 
                   segments_with_seconds[search_start_idx]['start_seconds'] < target_chunk_end_time * 0.9):
                search_start_idx += 1

            # 从搜索起点开始寻找超过阈值的停顿
            for segment_idx in range(search_start_idx, len(segments_with_seconds) - 1):
                current_segment = segments_with_seconds[segment_idx]
                next_segment = segments_with_seconds[segment_idx + 1]
                
                # 如果已经超出目标时间的110%，停止搜索
                if current_segment['start_seconds'] > target_chunk_end_time * 1.1:
                    break
                
                # 计算两个片段之间的停顿时间
                pause_duration = next_segment['start_seconds'] - current_segment['end_seconds']
                if pause_duration * 1000 >= pause_threshold_ms:
                    best_split_idx = segment_idx + 1  # 在停顿后切分
                    break
            
            # 如果没有找到合适的停顿点，在目标时间点强制切分
            if best_split_idx == -1:
                # 寻找最接近目标时间的片段
                segment_idx = chunk_start_idx
                while (segment_idx < len(segments_with_seconds) and 
                       segments_with_seconds[segment_idx]['start_seconds'] < target_chunk_end_time):
                    segment_idx += 1
                best_split_idx = segment_idx if segment_idx < len(segments_with_seconds) else len(segments_with_seconds)

            # 如果切分点无效或过小，将所有剩余部分作为一个块
            if best_split_idx <= chunk_start_idx:
                best_split_idx = len(segments_with_seconds)

            # 提取当前块的片段
            chunk_segments_with_seconds = segments_with_seconds[chunk_start_idx:best_split_idx]
            if not chunk_segments_with_seconds:
                break

            # 移除临时字段，得到干净的片段列表
            chunk_segments = []
            for segment_with_seconds in chunk_segments_with_seconds:
                clean_segment = segment_with_seconds.copy()
                del clean_segment['start_seconds']
                del clean_segment['end_seconds']
                chunk_segments.append(clean_segment)
            
            # 计算块的开始和结束时间
            chunk_start_time = chunk_segments[0]['start_time']
            chunk_end_time = chunk_segments[-1]['end_time']
            chunk_text = " ".join([segment['text'] for segment in chunk_segments])
            
            result_chunks.append({
                "chunk_index": chunk_idx,
                "text": chunk_text,
                "start_time": chunk_start_time,
                "end_time": chunk_end_time,
                "segments": chunk_segments
            })
            
            chunk_idx += 1
            last_chunk_end_time = chunk_segments_with_seconds[-1]['end_seconds']
            chunk_start_idx = best_split_idx
            
        return result_chunks
    
    def extract_outline(self, segments, analyzer, segment_duration_minutes: int = 30) -> List[EventItem]:
        logger.info("开始识别完整事件...")
        # 标准化segments格式
        normalized_segments = [asdict(seg) for seg in segments]
        if not normalized_segments:
            logger.warning("转写结果为空或格式异常，终止后续分析")
            return []

        # 使用智能分块将segments切分为多个块
        chunk_list = self._smart_chunk_segments(normalized_segments, segment_duration_minutes=segment_duration_minutes)
        if not chunk_list:
            logger.warning("未生成任何有效分块，终止后续分析")
            return []

        logger.info(f"转写结果按约 {segment_duration_minutes} 分钟切分，共 {len(chunk_list)} 个块")

        all_events: List[EventItem] = []
        for i, chunk in enumerate(chunk_list):
            logger.info(f"处理第 {i+1}/{len(chunk_list)} 个块...")
            
            # 从chunk中提取segments（chunk已经包含了segments字段）
            chunk_segments = chunk.get("segments", [])
            
            if not chunk_segments:
                logger.warning(f"第 {i+1} 个块没有对应的segments，跳过")
                continue

            # 准备输入数据
            input_data = {
                "segments": chunk_segments
            }
            # 调用 analyzer 进行事件识别（对外不再暴露 mode 字符串）
            logger.info(f"正在分析第 {i+1} 个块，包含 {len(chunk_segments)} 个转录片段...")
            response = analyzer.analyze_outline(input_data)
            if not response:
                logger.warning(f"处理第 {i+1} 个块时返回空响应")
                continue
            
            # 解析响应，获取事件列表
            logger.info(f"第 {i+1} 个块识别出 {len(response.events)} 个事件")
            all_events.extend(response.events)
        logger.info(f"事件识别完成，共识别出 {len(all_events)} 个完整事件")
        return all_events


class HighlightExtractorMixin:
    def extract_timeline(self, events: List[EventItem], analyzer) -> List[EventItem]:
        logger.info("开始筛选有趣事件...")

        if not events:
            logger.warning("事件列表为空，无法进行筛选")
            return []
        final_events: List[EventItem] = []

        for idx, event in enumerate(tqdm(events, desc="筛选事件", unit="件"), start=1):
            event_dict = event.model_dump()
            # 不传入 time 属性
            event_without_time = {k: v for k, v in event_dict.items() if k not in {"start_time", "end_time"}}
            input_data = {"events": [event_without_time]}
            # 对外使用语义化方法，不再传递字符串 mode
            response = analyzer.analyze_highlight(input_data)
            if not response:
                logger.warning(f"处理第 {idx+1} 个事件时返回空响应")
                continue
            # 由于每次只传递一个事件，命中项的 event_index 应为 0
            if response.is_highlight:
                event.llm_reason = response.reason
                final_events.append(event)

        logger.info(f"成功筛选出 {len(final_events)} 个有趣事件")
        return final_events

class OmniAudioUnderstandingMixin:
    _prompt = (
        "请判断音频中是否出现明显的搞笑、幽默或令人开心的情绪，"
        "只有当笑声或夸张语气很明显时才算有趣。"
        "请输出 JSON：{\"emotion\": \"\", \"reason\": \"\"}，emotion 只能是“有趣”或“无明显有趣”。"
    )
    _chunk_seconds = 20
    _base64_limit = 20_000_000
    _model_name = "qwen3-omni-flash"

    def omni_audio_understanding(self, events: List[EventItem]) -> Tuple[List[EventItem], List[EventItem]]:
        if not events:
            return [], []

        client = self._get_omni_client()
        audio = self._get_full_audio()
        if client is None or audio is None:
            return events, []

        passed: List[EventItem] = []
        rejected: List[EventItem] = []
        
        for event in events:
            start, end = self._get_event_range(event)
            logger.info(f'event: {event.title} --> start: {start}, end: {end}')
            if start is None:
                rejected.append(event.model_dump())
                continue

            is_funny = False
            for chunk in self._iter_chunks(audio, start, end):
                # print(f'chunk: {chunk}')
                payload = self._call_omni(client, chunk)
                logger.info(f'event: {event.title} --> payload: {payload}')
                if not payload:
                    continue
                if payload.get("emotion") == "有趣":
                    event.omni_reason = payload.get("reason", "")
                    is_funny = True
                    break

            (passed if is_funny else rejected).append(event)

        return rejected, passed

    def refine_events_with_omni(self, events: List[EventItem]) -> List[EventItem]:
        """
        对最终的事件列表做一次基于 omni 的精细处理：
        - 仅处理时长大于 60 秒的事件
        - 以 self._chunk_seconds 为窗口对事件内音频切片（当前为 20/30 秒）
        - 若某个切片被判定为「有趣」，则在该切片基础上各向前、向后扩展 5 秒，
          得到一个 [start, end] 有趣区间
        - 同一事件中多个有趣区间如有重叠则进行合并；不重叠则分别保留
        - 为每个不重叠有趣区间生成一个新的 EventItem，title 形如
          `原标题 有趣点1`、`原标题 有趣点2` ...
        """
        if not events:
            return []

        client = self._get_omni_client()
        audio = self._get_full_audio()
        if client is None or audio is None:
            # 如果 omni 不可用，直接返回原始结果
            return events

        refined_events: List[EventItem] = []

        for event in events:
            start, end = self._get_event_range(event)

            duration = end - start
            # 仅对大于 60 秒的事件做精细切分，其余直接保留
            if duration <= 60:
                refined_events.append(event)
                continue

            interesting_intervals: List[Tuple[float, float]] = []
            chunk_seconds = self._chunk_seconds

            offset = 0.0
            while start + offset < end:
                chunk_start = start + offset
                chunk_end = min(chunk_start + chunk_seconds, end)

                # 按绝对时间从整段音频中截取当前 chunk
                segment = audio[int(chunk_start * 1000): int(chunk_end * 1000)]
                if len(segment) == 0:
                    break

                payload = self._call_omni(client, segment)
                logger.info(
                    f"refine_events_with_omni | event: {event.title} | "
                    f"chunk: [{chunk_start:.2f}, {chunk_end:.2f}] | payload: {payload}"
                )

                if payload and payload.get("emotion") == "有趣":
                    # 在 chunk 的基础上前后各扩展 5 秒，限制在事件边界内
                    interesting_start = max(start, chunk_start - 5.0)
                    interesting_end = min(end, chunk_end + 5.0)
                    if interesting_end > interesting_start:
                        interesting_intervals.append((interesting_start, interesting_end))

                offset += chunk_seconds

            # 如果没有检测到任何有趣点，则保留原始事件
            if not interesting_intervals:
                # refined_events.append(event)
                continue

            # 合并重叠区间，确保得到的是互不重叠的多个有趣点
            interesting_intervals.sort(key=lambda x: x[0])
            merged_intervals: List[Tuple[float, float]] = []
            for s, e in interesting_intervals:
                if not merged_intervals or s > merged_intervals[-1][1]:
                    merged_intervals.append([s, e])
                else:
                    # 有重叠则合并
                    merged_intervals[-1][1] = max(merged_intervals[-1][1], e)

            # 为每个有趣点生成一个新的 EventItem
            base_data = event.model_dump()
            for idx, (s, e) in enumerate(merged_intervals, start=1):
                new_data = base_data.copy()
                new_data["start_time"] = float(s)
                new_data["end_time"] = float(e)
                new_data["title"] = f"{event.title} 有趣点{idx}"
                refined_events.append(EventItem(**new_data))

        return refined_events

    def _get_omni_client(self):
        if hasattr(self, "_omni_client"):
            return self._omni_client

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            logger.warning("缺少 DASHSCOPE_API_KEY 无法 omni 过滤")
            self._omni_client = None
            return None

        self._omni_client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        return self._omni_client

    def _get_full_audio(self, start_time=None, end_time=None):
        """
        根据事件的 start_time 和 end_time 裁剪音频片段
        如果 start_time 和 end_time 为 None，则返回完整音频
        """
        audio_path = getattr(self, "audio_path", None)
        if not audio_path:
            logger.warning("未找到音频路径，跳过 omni 过滤")
            return None

        try:
            audio = AudioSegment.from_file(audio_path)
        except Exception as e:
            logger.error(f"加载音频失败: {e}")
            return None

        if start_time is not None and end_time is not None:
            try:
                start_ms = int(float(start_time) * 1000)
                end_ms = int(float(end_time) * 1000)
                # 保证索引不越界
                start_ms = max(0, start_ms)
                end_ms = min(len(audio), end_ms)
                if end_ms > start_ms:
                    return audio[start_ms:end_ms]
                else:
                    logger.warning("end_time 小于等于 start_time，跳过裁剪")
                    return None
            except Exception as e:
                logger.error(f"音频裁剪失败: {e}")
                return None
        else:
            return audio

    def _get_event_range(self, event: EventItem):
        try:
            start = float(event.start_time)
            end = float(event.end_time)
        except (TypeError, ValueError):
            return None, None
        if end <= start:
            return None, None
        return max(0.0, start), end

    def _iter_chunks(self, audio: AudioSegment, start: float, end: float):
        segment = audio[int(start * 1000): int(end * 1000)]
        chunk_ms = self._chunk_seconds * 1000
        for offset in range(0, len(segment), chunk_ms):
            chunk = segment[offset: offset + chunk_ms]
            if len(chunk):
                yield chunk

    def _call_omni(self, client: OpenAI, chunk: AudioSegment):
        buffer = BytesIO()
        chunk.export(buffer, format="wav")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        if len(encoded) > self._base64_limit:
            return None

        completion = client.chat.completions.create(
            model=self._model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": f"data:;base64,{encoded}", "format": "wav"},
                        },
                        {"type": "text", "text": self._prompt},
                    ],
                }
            ],
        )
        content = completion.choices[0].message.content
        if content.startswith("```"):
            content = "\n".join(content.split("\n")[1:-1])
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None