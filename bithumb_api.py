"""
빗썸 API 클라이언트 모듈
KRW 마켓 종목 목록 조회, 캔들 데이터 조회 및 거래량 분석
"""
import requests
import logging
from typing import List, Dict, Optional, Any

# 로거 초기화 (모듈 레벨)
logger = logging.getLogger(__name__)


class BithumbAPI:
    """빗썸 공개 API 클라이언트"""
    
    BASE_URL = "https://api.bithumb.com/public"
    
    def __init__(self, timeout: int = 10):
        """
        Args:
            timeout: API 요청 타임아웃 (초 단위, 기본값: 10초)
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BithumbVolumeAlert/1.0'
        })
        self.timeout = timeout
    
    def get_krw_markets(self) -> List[str]:
        """
        KRW 마켓 상장 종목 목록 조회
        
        Returns:
            List[str]: 종목 코드 리스트 (예: ['BTC', 'ETH', 'XRP', ...])
        """
        try:
            url = f"{self.BASE_URL}/ticker/ALL_KRW"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                # 'date' 필드를 제외한 모든 키가 종목 코드
                markets = [code for code in data.get('data', {}).keys() if code != 'date']
                logger.debug(f"KRW 마켓 목록 조회 성공: {len(markets)}개 종목")
                return sorted(markets)
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.error(f"빗썸 API 오류 (KRW 마켓 목록): {error_msg}")
                return []
                
        except requests.exceptions.Timeout:
            logger.error(f"KRW 마켓 목록 조회 타임아웃 (timeout={self.timeout}초)")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"KRW 마켓 목록 조회 네트워크 오류: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"KRW 마켓 목록 조회 실패: {e}", exc_info=True)
            return []
    
    def get_candlestick(
        self, 
        order_currency: str, 
        payment_currency: str = "KRW",
        chart_intervals: str = "5m",
        count: int = 100
    ) -> Optional[List[Dict]]:
        """
        캔들 데이터 조회
        
        Args:
            order_currency: 주문 통화 (예: 'BTC')
            payment_currency: 결제 통화 (기본값: 'KRW')
            chart_intervals: 차트 간격 (기본값: '5m')
                            지원 형식: '1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d' 등
            count: 조회할 캔들 개수 (기본값: 100)
            
        Returns:
            List[Dict]: 캔들 데이터 리스트
            각 캔들은 다음과 같은 형식:
            {
                'time': timestamp (밀리초),
                'open': 시작가,
                'close': 종가,
                'high': 최고가,
                'low': 최저가,
                'volume': 거래량
            }
        """
        try:
            url = f"{self.BASE_URL}/candlestick/{order_currency}_{payment_currency}/{chart_intervals}"
            params = {
                'count': count
            }
            
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                candles = data.get('data', [])
                parsed_candles = self._parse_candles(candles)
                logger.debug(f"{order_currency} 캔들 데이터 조회 성공: {len(parsed_candles)}개")
                return parsed_candles
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.warning(f"캔들 데이터 조회 실패 ({order_currency}): {error_msg}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"{order_currency} 캔들 데이터 조회 타임아웃 (timeout={self.timeout}초)")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"{order_currency} 캔들 데이터 조회 네트워크 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"{order_currency} 캔들 데이터 조회 중 오류: {e}", exc_info=True)
            return None
    
    def _parse_candles(self, raw_data: List) -> List[Dict]:
        """
        빗썸 API 응답 데이터를 표준 형식으로 변환
        
        Args:
            raw_data: API 응답 원본 데이터
            
        Returns:
            List[Dict]: 파싱된 캔들 데이터 리스트
        """
        parsed = []
        for candle in raw_data:
            if isinstance(candle, list) and len(candle) >= 6:
                parsed.append({
                    'time': candle[0],
                    'open': float(candle[1]),
                    'close': float(candle[2]),
                    'high': float(candle[3]),
                    'low': float(candle[4]),
                    'volume': float(candle[5])
                })
            elif isinstance(candle, dict):
                parsed.append({
                    'time': candle.get('time', candle.get('dt', 0)),
                    'open': float(candle.get('open', candle.get('openPrice', 0))),
                    'close': float(candle.get('close', candle.get('closePrice', 0))),
                    'high': float(candle.get('high', candle.get('highPrice', 0))),
                    'low': float(candle.get('low', candle.get('lowPrice', 0))),
                    'volume': float(candle.get('volume', candle.get('transactions', 0)))
                })
        
        # 시간 순서대로 정렬 (오래된 것부터)
        parsed.sort(key=lambda x: x['time'])
        return parsed
    
    def get_current_ticker(self, order_currency: str, payment_currency: str = "KRW") -> Optional[Dict]:
        """
        현재 시세 정보 조회 (실시간 거래량 포함)
        
        Args:
            order_currency: 주문 통화 (예: 'BTC')
            payment_currency: 결제 통화 (기본값: 'KRW')
            
        Returns:
            Dict: 현재 시세 정보
        """
        try:
            url = f"{self.BASE_URL}/ticker/{order_currency}_{payment_currency}"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == '0000':
                return data.get('data', {})
            else:
                error_msg = data.get('message', 'Unknown error')
                logger.warning(f"시세 조회 실패 ({order_currency}): {error_msg}")
                return None
                
        except requests.exceptions.Timeout:
            logger.warning(f"{order_currency} 시세 조회 타임아웃 (timeout={self.timeout}초)")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"{order_currency} 시세 조회 네트워크 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"시세 조회 실패 ({order_currency}): {e}", exc_info=True)
            return None


class VolumeAnalyzer:
    """거래량 분석기"""
    
    def __init__(self, sma_period: int = 20, volume_multiplier: float = 5.0):
        """
        Args:
            sma_period: 이동평균 계산 기간 (기본값: 20)
            volume_multiplier: 알림을 위한 거래량 배수 (기본값: 5.0)
        """
        self.sma_period = sma_period
        self.volume_multiplier = volume_multiplier
    
    def calculate_volume_sma(self, candles: List[Dict]) -> Optional[float]:
        """
        거래량의 SMA 계산
        
        Args:
            candles: 캔들 데이터 리스트 (최소 sma_period개 이상 권장)
            
        Returns:
            float: 거래량 SMA 값, 계산 불가능하면 None
        """
        if not candles or len(candles) < self.sma_period:
            return None
        
        # 최근 N개의 거래량 추출
        volumes = [candle['volume'] for candle in candles[-self.sma_period:]]
        
        # SMA 계산
        sma = sum(volumes) / len(volumes)
        return sma
    
    def check_volume_spike(
        self, 
        candles: List[Dict], 
        current_volume: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        현재 거래량이 평균 대비 배수 이상인지 확인
        
        Args:
            candles: 캔들 데이터 리스트
            current_volume: 현재 거래량 (없으면 최신 캔들의 거래량 사용)
            
        Returns:
            Dict: 분석 결과
            {
                'is_spike': bool,  # 배수 이상인지 여부
                'current_volume': float,  # 현재 거래량
                'sma_volume': float,  # SMA 거래량
                'multiplier': float,  # 배수 (current_volume / sma_volume)
                'candles_needed': int  # 필요한 캔들 개수
            }
        """
        result = {
            'is_spike': False,
            'current_volume': 0.0,
            'sma_volume': 0.0,
            'multiplier': 0.0,
            'candles_needed': self.sma_period
        }
        
        if not candles:
            return result
        
        # 현재 거래량 결정
        if current_volume is None:
            # 최신 캔들의 거래량 사용
            result['current_volume'] = candles[-1]['volume']
        else:
            result['current_volume'] = current_volume
        
        # SMA 계산
        sma_volume = self.calculate_volume_sma(candles)
        if sma_volume is None or sma_volume == 0:
            result['candles_needed'] = self.sma_period - len(candles)
            return result
        
        result['sma_volume'] = sma_volume
        result['multiplier'] = result['current_volume'] / sma_volume
        result['is_spike'] = result['multiplier'] >= self.volume_multiplier
        
        return result
    
    def analyze_market(
        self, 
        candles: List[Dict],
        symbol: str
    ) -> Optional[Dict]:
        """
        종목의 거래량 스파이크 분석
        
        Args:
            candles: 캔들 데이터 리스트
            symbol: 종목 코드
            
        Returns:
            Dict: 분석 결과 (스파이크가 없으면 None)
        """
        if not candles:
            return None
        
        analysis = self.check_volume_spike(candles)
        
        if analysis['is_spike']:
            return {
                'symbol': symbol,
                'current_volume': analysis['current_volume'],
                'sma_volume': analysis['sma_volume'],
                'multiplier': analysis['multiplier'],
                'current_price': candles[-1]['close'],
                'timestamp': candles[-1]['time']
            }
        
        return None

