import os
import logging
from typing import List
from moviepy.editor import VideoFileClip, concatenate_videoclips

logger = logging.getLogger(__name__)


class VideoMerger:
    def __init__(self):
        """Initialize video merger."""
        self.temp_dir = os.getenv("TEMP_DIR", "./temp")
        os.makedirs(self.temp_dir, exist_ok=True)

    async def merge_videos(self, video_paths: List[str], output_path: str) -> str:
        """
        Merge multiple video files into a single MP4 file.

        Args:
            video_paths: List of paths to video files to merge
            output_path: Path where the merged video will be saved

        Returns:
            Path to the merged video file
        """
        clips = []

        try:
            logger.info(f"Loading {len(video_paths)} video clips...")

            # Load all video clips
            for i, video_path in enumerate(video_paths):
                if not os.path.exists(video_path):
                    raise FileNotFoundError(f"Video file not found: {video_path}")

                if not video_path.lower().endswith(".mp4"):
                    raise ValueError(f"Only MP4 files are supported. Got: {video_path}")

                try:
                    clip = VideoFileClip(video_path)
                    clips.append(clip)
                    logger.info(
                        f"Loaded clip {i + 1}/{len(video_paths)}: {video_path} (duration: {clip.duration:.2f}s)"
                    )
                except Exception as e:
                    logger.error(f"Failed to load video clip {video_path}: {str(e)}")
                    raise ValueError(
                        f"Failed to load video clip {video_path}: {str(e)}"
                    )

            if not clips:
                raise ValueError("No valid video clips to merge")

            # Ensure all clips have the same fps and size for consistency
            logger.info("Standardizing video properties...")
            standardized_clips = []

            # Use the first clip's properties as reference
            reference_clip = clips[0]
            target_fps = reference_clip.fps
            target_size = reference_clip.size

            logger.info(f"Target properties - FPS: {target_fps}, Size: {target_size}")

            for i, clip in enumerate(clips):
                try:
                    # Resize if necessary
                    if clip.size != target_size:
                        logger.info(
                            f"Resizing clip {i + 1} from {clip.size} to {target_size}"
                        )
                        clip = clip.resize(target_size)

                    # Adjust fps if necessary
                    if abs(clip.fps - target_fps) > 0.1:  # Allow small fps differences
                        logger.info(
                            f"Adjusting FPS for clip {i + 1} from {clip.fps} to {target_fps}"
                        )
                        clip = clip.set_fps(target_fps)

                    standardized_clips.append(clip)

                except Exception as e:
                    logger.error(f"Failed to standardize clip {i + 1}: {str(e)}")
                    # Use original clip if standardization fails
                    standardized_clips.append(clip)

            # Concatenate all clips
            logger.info("Concatenating video clips...")
            final_clip = concatenate_videoclips(standardized_clips, method="compose")

            logger.info(f"Final video duration: {final_clip.duration:.2f} seconds")

            # Write the final video
            logger.info(f"Writing merged video to: {output_path}")
            final_clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile="temp-audio.m4a",
                remove_temp=True,
                verbose=False,
                logger=None,  # Disable moviepy's own logging to avoid clutter
            )

            # Verify the output file
            if not os.path.exists(output_path):
                raise Exception("Failed to create merged video file")

            file_size = os.path.getsize(output_path)
            if file_size == 0:
                raise Exception("Merged video file is empty")

            logger.info(
                f"Successfully created merged video: {output_path} (size: {file_size / (1024 * 1024):.2f} MB)"
            )

            return output_path

        except Exception as e:
            logger.error(f"Error during video merging: {str(e)}")
            # Clean up output file if it exists but is invalid
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            raise

        finally:
            # Clean up clip objects to free memory
            for clip in clips:
                try:
                    clip.close()
                except:
                    pass

            try:
                if "final_clip" in locals():
                    final_clip.close()
            except:
                pass

    def get_video_info(self, video_path: str) -> dict:
        """
        Get information about a video file.

        Args:
            video_path: Path to the video file

        Returns:
            Dictionary containing video information
        """
        try:
            clip = VideoFileClip(video_path)
            info = {
                "duration": clip.duration,
                "fps": clip.fps,
                "size": clip.size,
                "file_size": os.path.getsize(video_path),
            }
            clip.close()
            return info
        except Exception as e:
            logger.error(f"Failed to get video info for {video_path}: {str(e)}")
            return {}
