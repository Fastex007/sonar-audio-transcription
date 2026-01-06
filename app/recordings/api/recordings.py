import os
import uuid
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from ninja import Router, File, Form
from ninja.files import UploadedFile

logger = logging.getLogger(__name__)

router = Router()

# Store active recording sessions
active_recordings = {}


@router.post("/start-recording")
def start_recording(request):
    session_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{timestamp}_{session_id[:8]}.wav"

    # Create directory for this session's chunks
    chunks_dir = os.path.join(settings.MEDIA_ROOT, "chunks", session_id)
    os.makedirs(chunks_dir, exist_ok=True)

    # Final file location
    filepath = os.path.join(settings.MEDIA_ROOT, "recordings", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    active_recordings[session_id] = {
        'filepath': filepath,
        'filename': filename,
        'chunks_dir': chunks_dir,
        'chunk_count': 0,
        'started_at': datetime.now().isoformat()
    }

    return {
        'session_id': session_id,
        'filename': filename,
        'status': 'started'
    }


@router.post("/upload-chunk/{session_id}")
def upload_chunk(request, session_id: str, chunk: UploadedFile = File(...), chunk_number: int = Form(...)):
    if session_id not in active_recordings:
        return JsonResponse({'error': 'Invalid session_id'}, status=404)

    recording_info = active_recordings[session_id]
    chunks_dir = recording_info['chunks_dir']

    # Save chunk with zero-padded number for proper sorting
    chunk_filename = f"chunk_{chunk_number:04d}.wav"
    chunk_filepath = os.path.join(chunks_dir, chunk_filename)

    # Write chunk to file
    with open(chunk_filepath, 'wb') as f:
        for chunk_data in chunk.chunks():
            f.write(chunk_data)

    # Update chunk count
    recording_info['chunk_count'] = max(recording_info['chunk_count'], chunk_number)

    logger.debug(f"WAV Chunk {chunk_number} saved: {chunk_filename} ({os.path.getsize(chunk_filepath)} bytes)")

    return {
        'status': 'chunk_received',
        'session_id': session_id,
        'chunk_number': chunk_number
    }


@router.post("/stop-recording/{session_id}")
def stop_recording(request, session_id: str):
    if session_id not in active_recordings:
        return JsonResponse({'error': 'Invalid session_id'}, status=404)

    recording_info = active_recordings.pop(session_id)
    chunks_dir = recording_info['chunks_dir']
    final_file = recording_info['filepath']
    chunk_count = recording_info['chunk_count']

    logger.info(f"Stopping recording, concatenating {chunk_count} WAV chunks...")

    try:
        # Get all chunk files sorted by number
        chunk_files = sorted([
            os.path.join(chunks_dir, f)
            for f in os.listdir(chunks_dir)
            if f.startswith('chunk_') and f.endswith('.wav')
        ])

        if not chunk_files:
            logger.warning("No chunks found, creating empty file")
            open(final_file, 'wb').close()
        elif len(chunk_files) == 1:
            # Only one chunk, just copy it
            logger.info("Only one chunk, copying directly...")
            import shutil
            shutil.copy2(chunk_files[0], final_file)
        else:
            # Multiple chunks - concatenate WAV files
            logger.info(f"Concatenating {len(chunk_files)} WAV chunks...")
            concatenate_wav_files(chunk_files, final_file)
            logger.info(f"Successfully concatenated {len(chunk_files)} WAV chunks")

        # Cleanup chunks directory
        import shutil
        shutil.rmtree(chunks_dir)
        logger.info(f"Cleaned up chunks directory")

    except Exception as e:
        logger.error(f"Error processing chunks: {str(e)}", exc_info=True)
        # Try to create at least something from first chunk if available
        chunk_files = [f for f in os.listdir(chunks_dir) if f.endswith('.wav')]
        if chunk_files:
            import shutil
            shutil.copy2(os.path.join(chunks_dir, chunk_files[0]), final_file)

    return {
        'status': 'stopped',
        'session_id': session_id,
        'filename': recording_info['filename'],
        'filepath': final_file,
        'chunks_processed': chunk_count
    }


def concatenate_wav_files(input_files, output_file):
    with open(input_files[0], 'rb') as f:
        header = bytearray(f.read(44))

    # Collect all PCM data
    pcm_data = bytearray()
    for wav_file in input_files:
        with open(wav_file, 'rb') as f:
            f.read(44)  # Skip WAV header
            pcm_data.extend(f.read())

    # Update file size in header
    # Total file size = 36 + data size
    import struct
    total_size = 36 + len(pcm_data)
    struct.pack_into('<I', header, 4, total_size)

    # Update data chunk size
    struct.pack_into('<I', header, 40, len(pcm_data))

    # Write final file
    with open(output_file, 'wb') as f:
        f.write(header)
        f.write(pcm_data)

    logger.debug(f"Created WAV file: {len(pcm_data)} bytes PCM data")


@router.get("/recordings")
def list_recordings(request):
    recordings_dir = os.path.join(settings.MEDIA_ROOT, "recordings")

    if not os.path.exists(recordings_dir):
        return {'recordings': []}

    recordings = []
    for filename in os.listdir(recordings_dir):
        if filename.endswith(('.wav', '.webm', '.mp3')):
            filepath = os.path.join(recordings_dir, filename)
            stat = os.stat(filepath)
            recordings.append({
                'filename': filename,
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'url': f"/media/recordings/{filename}"
            })

    recordings.sort(key=lambda x: x['created_at'], reverse=True)
    return {'recordings': recordings}


from django.http import StreamingHttpResponse
import mimetypes

def range_response(request, filepath, content_type):
    file_size = os.path.getsize(filepath)
    range_header = request.META.get('HTTP_RANGE', '').strip()
    range_match = None

    if range_header:
        import re
        range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)

    if range_match:
        # Partial content request
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        length = end - start + 1

        def file_iterator(start, length):
            with open(filepath, 'rb') as f:
                f.seek(start)
                remaining = length
                chunk_size = 8192
                while remaining > 0:
                    chunk = f.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        response = StreamingHttpResponse(
            file_iterator(start, length),
            status=206,
            content_type=content_type
        )
        response['Content-Length'] = length
        response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
        response['Accept-Ranges'] = 'bytes'

    else:
        # Full file request
        response = FileResponse(
            open(filepath, 'rb'),
            content_type=content_type,
            as_attachment=False
        )
        response['Content-Length'] = file_size
        response['Accept-Ranges'] = 'bytes'

    return response


@router.get("/play/{filename}", include_in_schema=True)
def play_recording(request, filename: str):
    filepath = os.path.join(settings.MEDIA_ROOT, "recordings", filename)

    if not os.path.exists(filepath):
        return HttpResponse("File not found", status=404)

    # Determine content type
    content_type = 'audio/webm'
    if filename.endswith('.wav'):
        content_type = 'audio/wav'
    elif filename.endswith('.mp3'):
        content_type = 'audio/mpeg'

    return range_response(request, filepath, content_type)


@router.delete("/delete/{filename}")
def delete_recording(request, filename: str):
    filepath = os.path.join(settings.MEDIA_ROOT, "recordings", filename)

    if not os.path.exists(filepath):
        return JsonResponse({'error': 'File not found'}, status=404)

    os.remove(filepath)
    return {'status': 'deleted', 'filename': filename}
