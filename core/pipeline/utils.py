from typing import List, Dict,Any
from loguru import logger
from tqdm import tqdm
import json

class OutlineExtractorMixin:
    def __init__(self):
        pass

    def _parse_outline_response(self, response: str) -> List[Dict]:
        """
        解析事件识别响应，返回事件列表（包含时间戳）
        """
        events = []
        try:
            # 解析响应文本
            if isinstance(response, dict):
                response_text = response.get("response", response.get("content", ""))
            else:
                response_text = response
            
            # 清理响应文本，移除可能的markdown代码块标记
            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            elif response_text.startswith("```json"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            
            # 解析JSON字符串
            data = json.loads(response_text)
            
            # 遍历事件列表
            for item in data.get("events", []):
                current_event = {
                    "title": item.get("title", ""),
                    "description": item.get("description", ""),
                    "start_time": float(item.get("start_time", 0)),
                    "end_time": float(item.get("end_time", 0)),
                    "content": item.get("content", "")
                }
                events.append(current_event)
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {e}")
            logger.error(f"响应内容: {response_text[:500] if 'response_text' in locals() else str(response)[:500]}")
        except Exception as e:
            logger.error(f"解析事件响应时发生错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        logger.info(f"解析出 {len(events)} 个事件")
        return events

    def _merge_outlines(self, outlines: List[Dict]) -> List[Dict]:
        """
        合并和去重大纲，保留最先出现的版本
        """
        unique_outlines = {}
        for outline in outlines:
            title = outline['title']
            if title not in unique_outlines:
                unique_outlines[title] = outline
        return list(unique_outlines.values())

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
    
    def extract_outline(self, segments, analyzer, segment_duration_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        从转录文本和时间戳中识别完整事件，返回包含时间戳的事件列表
        
        参数:
            segments: 转录文本片段列表
            analyzer: 分析器对象
            interval_minutes: 分块时间间隔（分钟），默认30分钟
        """
        logger.info("开始识别完整事件...")
        
        # 标准化segments格式
        normalized_segments = [seg.to_dict() for seg in segments]
        if not normalized_segments:
            logger.warning("转写结果为空或格式异常，终止后续分析")
            return []

        # 使用智能分块将segments切分为多个块
        chunk_list = self._smart_chunk_segments(normalized_segments, segment_duration_minutes=segment_duration_minutes)

        if not chunk_list:
            logger.warning("未生成任何有效分块，终止后续分析")
            return []

        logger.info(f"转写结果按约 {segment_duration_minutes} 分钟切分，共 {len(chunk_list)} 个块")

        all_events: List[Dict[str, Any]] = []
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
            
            # 调用analyzer进行事件识别
            logger.info(f"正在分析第 {i+1} 个块，包含 {len(chunk_segments)} 个转录片段...")
            response = analyzer.analyze(input_data, mode="outline")
            
            if not response:
                logger.warning(f"处理第 {i+1} 个块时返回空响应")
                continue
            
            # 解析响应，获取事件列表
            chunk_events = self._parse_outline_response(response)
            logger.info(f"第 {i+1} 个块识别出 {len(chunk_events)} 个事件")
            all_events.extend(chunk_events)


        logger.info(f"事件识别完成，共识别出 {len(all_events)} 个完整事件")
        return all_events
    


class TimelineExtractorMixin:
    def __init__(self):
        pass

    def extract_timeline(self, events: List[Dict], analyzer) -> List[Dict]:
        """
        从事件列表中筛选出哈哈笑、家庭欢快有趣的事件。
        
        新版特性：
        - 接收已识别的事件列表（包含时间戳）
        - 筛选出符合"哈哈笑、家庭欢快有趣"标准的事件
        """
        logger.info("开始筛选有趣事件...")

        if not events:
            logger.warning("事件列表为空，无法进行筛选")
            return []

        final_events: List[Dict] = []

        for idx, event in enumerate(tqdm(events, desc="筛选事件", unit="件"), start=1):
            event_without_time = {
                key: value
                for key, value in event.items()
                if key not in {"start_time", "end_time"}
            }

            input_data = {"events": [event_without_time]}

            raw_response = analyzer.analyze(input_data, mode='highlight')

            if isinstance(raw_response, dict):
                response_text = raw_response.get("response", raw_response.get("content", ""))
            else:
                response_text = raw_response

            response_text = response_text.strip()
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
            elif response_text.startswith("```json"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text

            output_items = json.loads(response_text).get("output", [])

            # 由于每次只传递一个事件，命中项的 event_index 应为 0
            for item in output_items:
                if item.get('event_index') == 0:
                    print(f'event_llm_happy:{event}')
                    print(f'reason:{item.get("reason")}')
                    final_events.append(event)

        logger.info(f"成功筛选出 {len(final_events)} 个有趣事件")
        return final_events