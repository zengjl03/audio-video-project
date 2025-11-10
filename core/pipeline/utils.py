import re
from typing import List, Dict,Any,Optional
from loguru import logger
import json
from collections import defaultdict
from pathlib import Path

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

    def _normalize_segments(self, segments: List[List[Any]]) -> List[Dict[str, Any]]:
        """将模型转写结果标准化为统一结构"""
        normalized = []
        for idx, segment in enumerate(segments):
            text, start, end = segment
            normalized.append({
                "index": idx,
                "text": text,
                "start_time": float(start),
                "end_time": float(end)
            })
        return normalized

    def _smart_chunk_segments(self, segments: List[Dict[str, Any]],interval_minutes:int = 30,pause_threshold_ms: float = 1000.0) -> List[Dict[str, Any]]:
        """参照 autoclip 的时间智能分块逻辑，将转写片段切分为均匀时间块"""
        if not segments:
            return []

        # 创建一个带有秒数的新列表，而不是修改原始数据
        srt_data_with_seconds = []
        for sub in segments:
            entry = sub.copy()
            entry['start_seconds'] = sub['start_time']
            entry['end_seconds'] = sub['end_time']
            srt_data_with_seconds.append(entry)

        interval_seconds = interval_minutes * 60
        chunks = []
        current_chunk_start_index = 0
        chunk_index = 0
        
        last_cut_time = 0
        
        while current_chunk_start_index < len(srt_data_with_seconds):
            target_cut_time = last_cut_time + interval_seconds
            
            # 寻找接近目标时间的最佳切分点
            best_cut_index = -1
            
            # 查找从当前块开始后的 90% 到 110% 目标时间内的一个停顿
            search_start_index = current_chunk_start_index
            while search_start_index < len(srt_data_with_seconds) and srt_data_with_seconds[search_start_index]['start_seconds'] < target_cut_time * 0.9:
                search_start_index += 1

            # 从搜索起点开始寻找超过阈值的停顿
            for i in range(search_start_index, len(srt_data_with_seconds) - 1):
                current_sub = srt_data_with_seconds[i]
                next_sub = srt_data_with_seconds[i+1]
                
                # 如果我们已经超出了目标时间的110%，就停止搜索
                if current_sub['start_seconds'] > target_cut_time * 1.1:
                    break
                
                # 计算两个字幕条目之间的停顿时间
                pause = next_sub['start_seconds'] - current_sub['end_seconds']
                if pause * 1000 >= pause_threshold_ms:
                    best_cut_index = i + 1  # 在停顿后切分
                    break
            
            # 如果没有找到合适的停顿点，就在目标时间点强制切分
            if best_cut_index == -1:
                # 寻找最接近目标时间的字幕条目
                i = current_chunk_start_index
                while i < len(srt_data_with_seconds) and srt_data_with_seconds[i]['start_seconds'] < target_cut_time:
                    i += 1
                best_cut_index = i if i < len(srt_data_with_seconds) else len(srt_data_with_seconds)

            # 如果切分点无效或过小，则将所有剩余部分作为一个块
            if best_cut_index <= current_chunk_start_index:
                 best_cut_index = len(srt_data_with_seconds)

            # 创建块
            chunk_entries_with_seconds = srt_data_with_seconds[current_chunk_start_index:best_cut_index]
            if not chunk_entries_with_seconds:
                break

            # 移除临时字段，得到干净的srt_entries
            chunk_entries = []
            for entry in chunk_entries_with_seconds:
                clean_entry = entry.copy()
                del clean_entry['start_seconds']
                del clean_entry['end_seconds']
                chunk_entries.append(clean_entry)
            
            start_time = chunk_entries[0]['start_time']
            end_time = chunk_entries[-1]['end_time']
            text = " ".join([entry['text'] for entry in chunk_entries])
            
            chunks.append({
                "chunk_index": chunk_index,
                "text": text,
                "start_time": start_time,
                "end_time": end_time
            })
            
            chunk_index += 1
            last_cut_time = chunk_entries_with_seconds[-1]['end_seconds']
            current_chunk_start_index = best_cut_index
            
        return chunks
    
    def extract_outline(self, segments, analyzer):
        """
        从转录文本和时间戳中识别完整事件，返回包含时间戳的事件列表
        """
        logger.info("开始识别完整事件...")
        
        # 标准化segments格式
        normalized_segments = self._normalize_segments(segments)
        if not normalized_segments:
            logger.warning("转写结果为空或格式异常，终止后续分析")
            return []

        # 准备输入数据
        input_data = {
            "segments": normalized_segments
        }

        try:
            # 调用analyzer进行事件识别
            logger.info(f"正在分析 {len(normalized_segments)} 个转录片段...")
            response = analyzer.analyze(input_data, mode="outline")
            
            if not response:
                logger.warning("事件识别返回空响应")
                return []
            
            # 解析响应，获取事件列表
            events = self._parse_outline_response(response)
            
            logger.info(f"事件识别完成，共识别出 {len(events)} 个完整事件")
            return events
            
        except Exception as e:
            logger.error(f"处理事件识别时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    


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

        try:
            # 准备输入数据：将所有事件传递给analyzer进行筛选
            input_data = {
                "events": events
            }

            # 调用analyzer进行事件筛选
            logger.info(f"正在筛选 {len(events)} 个事件...")
            raw_response = analyzer.analyze(input_data, mode='highlight')
            
            # 解析响应
            if isinstance(raw_response, dict):
                # 如果是字典格式，尝试提取response字段
                response_text = raw_response.get("response", raw_response.get("content", ""))
            else:
                response_text = raw_response

            # 尝试解析JSON响应
            try:
                # 清理响应文本，移除可能的markdown代码块标记
                response_text = response_text.strip()
                if response_text.startswith("```"):
                    # 移除markdown代码块标记
                    lines = response_text.split("\n")
                    response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
                elif response_text.startswith("```json"):
                    lines = response_text.split("\n")
                    response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text
                
                filtered_events = json.loads(response_text)
                
                # 确保返回的是列表
                if isinstance(filtered_events, dict):
                    # 如果返回的是字典，尝试提取output或events字段
                    filtered_events = filtered_events.get("output", filtered_events.get("events", []))
                
                if not isinstance(filtered_events, list):
                    logger.warning(f"解析后的响应不是列表格式: {type(filtered_events)}")
                    filtered_events = []
                
                logger.info(f"成功筛选出 {len(filtered_events)} 个有趣事件")
                return filtered_events
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析错误: {e}")
                logger.error(f"响应内容: {response_text[:500]}")  # 只打印前500个字符
                return []
                
        except Exception as e:
            logger.error(f"处理事件筛选时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []